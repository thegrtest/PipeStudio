"""Small independent fixtures exercise corrupt exports and detector edge cases."""
import json
from pathlib import Path
import tempfile
import unittest

from PIL import Image, ImageChops, ImageDraw

from dataset_tools import (atomic_json, evaluate_dataset, export_coco,
                           groups_and_splits, report_dataset, validate_dataset)


class DatasetToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.samples = []
        for folder in ("images", "masks", "labels", "metadata"):
            (self.root / folder).mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def sample(self, stem, kind="DENT", box=(10, 5, 20, 10), **extra):
        if kind in ("NONE", "CLEAN"):
            box = None
        width, height = 80, 40
        Image.new("RGB", (width, height), (127, 111, 72)).save(self.root / "images" / f"{stem}.png")
        mask = Image.new("L", (width, height), 0)
        if box:
            x, y, w, h = box
            ImageDraw.Draw(mask).rectangle((x, y, x + w - 1, y + h - 1), fill=255)
        mask.save(self.root / "masks" / f"{stem}.png")
        class_id = {"NONE": None, "CLEAN": None, "DENT": 1, "FOLD": 0}[kind]
        text = ""
        if box:
            text = f"{class_id} {(x + w / 2) / width:.8f} {(y + h / 2) / height:.8f} {w / width:.8f} {h / height:.8f}\n"
        (self.root / "labels" / f"{stem}.txt").write_text(text, encoding="utf-8")
        data = {"image": f"images/{stem}.png", "mask": f"masks/{stem}.png", "width": width, "height": height,
                "class_id": class_id, "defect_type": kind, "bbox_xywh": list(box) if box else None,
                "visible_mask_pixels": box[2] * box[3] if box else 0,
                "has_visible_geometric_mask": bool(box), "parameters": {"environment": "MACHINE"}}
        atomic_json(self.root / "metadata" / f"{stem}.json", data)
        data.update(extra)
        self.samples.append(data)
        atomic_json(self.root / "manifest.json", {"classes": {"0": "Fold", "1": "Dent"}, "samples": self.samples})
        return data

    def predictions(self, rows):
        path = self.root / "predictions.json"
        atomic_json(path, rows)
        return path

    def test_visible_clean_and_hidden_are_valid(self):
        self.sample("visible", specimen_id="part1")
        self.sample("clean", "NONE", specimen_id="part2")
        self.sample("hidden", "FOLD", None, specimen_id="part3")
        result = validate_dataset(self.root)
        self.assertTrue(result["valid"], result)
        self.assertEqual(result["sample_count"], 3)
        self.assertEqual(result["warnings"], [])

    def test_binary_mask_and_metadata_are_actually_checked(self):
        self.sample("bad")
        image = Image.open(self.root / "masks" / "bad.png").copy()
        image.putpixel((0, 0), 128)
        image.save(self.root / "masks" / "bad.png")
        result = validate_dataset(self.root)
        self.assertFalse(result["valid"])
        self.assertTrue(any("binary" in error for error in result["errors"]))

    def test_wrong_normalized_box_and_extra_images_fail(self):
        self.sample("bad")
        (self.root / "labels" / "bad.txt").write_text("1 0.5 0.5 0.25 0.25\n", encoding="utf-8")
        Image.new("RGB", (80, 40)).save(self.root / "images" / "unlisted.png")
        result = validate_dataset(self.root)
        self.assertFalse(result["valid"])
        self.assertTrue(any("YOLO box disagrees" in error for error in result["errors"]))
        self.assertTrue(any("Unlisted images" in error for error in result["errors"]))

    def test_clean_with_label_is_rejected(self):
        self.sample("clean", "CLEAN")
        (self.root / "labels" / "clean.txt").write_text("0 0.5 0.5 0.1 0.1", encoding="utf-8")
        result = validate_dataset(self.root)
        self.assertFalse(result["valid"])
        self.assertTrue(any("empty YOLO" in error for error in result["errors"]))

    def test_path_escape_does_not_read_outside_dataset(self):
        self.sample("safe")
        self.samples[0]["image"] = "images/../../private.png"
        atomic_json(self.root / "manifest.json", {"samples": self.samples})
        result = validate_dataset(self.root)
        self.assertFalse(result["valid"])
        self.assertTrue(any("escapes" in error for error in result["errors"]))

    def test_group_splits_reject_leakage_and_keep_pairs_together(self):
        self.sample("first", specimen_id="same", split="train")
        self.sample("second", specimen_id="same", split="test")
        self.assertFalse(validate_dataset(self.root)["valid"])
        self.samples[1].pop("split")
        result = groups_and_splits(self.samples, (.5, .25, .25))
        self.assertEqual(set(result.values()), {"train"})
        for sample in self.samples:
            sample.pop("split", None)
        self.assertEqual(len(set(groups_and_splits(self.samples, (.5, .25, .25)).values())), 1)
        self.assertEqual(groups_and_splits(self.samples), groups_and_splits(list(reversed(self.samples))))

    def test_coco_has_boxes_only_and_preserves_zero_based_class_ids(self):
        self.sample("fold", "FOLD", specimen_id="one", split="val")
        self.sample("clean", "CLEAN", specimen_id="two")
        result = export_coco(self.root)
        self.assertEqual(result["counts"], {"train": 0, "val": 1, "test": 1})
        coco = json.loads((self.root / "annotations.coco.json").read_text())
        self.assertEqual(coco["annotations"][0]["bbox"], [10, 5, 20, 10])
        self.assertEqual(coco["annotations"][0]["category_id"], 0)
        self.assertNotIn("segmentation", coco["annotations"][0])
        self.assertEqual(len(coco["annotations"]), 1)
        self.assertIn("test: splits/test.txt", (self.root / "dataset.yaml").read_text())

    def test_duplicate_wrong_class_and_empty_gt_predictions_are_false_positives(self):
        self.sample("dent", lighting_profile="raking", scenario_id="dents")
        self.sample("clean", "CLEAN", lighting_profile="bright", scenario_id="negatives")
        self.sample("missed", "FOLD", lighting_profile="raking", scenario_id="folds")
        rows = [
            {"image_id": 1, "category_id": 0, "bbox": [10, 5, 20, 10], "score": .99},
            {"image_id": 1, "category_id": 1, "bbox": [10, 5, 20, 10], "score": .9},
            {"image_id": 1, "category_id": 1, "bbox": [10, 5, 20, 10], "score": .8},
            {"image_id": 2, "category_id": 1, "bbox": [1, 1, 3, 3], "score": .8},
            {"image_id": 3, "category_id": 0, "bbox": [10, 5, 20, 10], "score": .1}]
        result = evaluate_dataset(self.root, self.predictions(rows))
        self.assertEqual(result["overall"], {"images": 3, "tp": 1, "fp": 3, "fn": 1, "precision": .25, "recall": .5})
        self.assertEqual(result["by"]["lighting"]["bright"]["fp"], 1)
        self.assertEqual(result["by"]["scenario"]["folds"]["fn"], 1)

    def test_all_clean_empty_predictions_have_undefined_precision_and_recall(self):
        self.sample("clean", "CLEAN")
        self.sample("hidden", "DENT", None)
        result = evaluate_dataset(self.root, self.predictions([]))
        self.assertEqual(result["overall"]["tp"], 0)
        self.assertEqual(result["overall"]["fn"], 0)
        self.assertIsNone(result["overall"]["precision"])
        self.assertIsNone(result["overall"]["recall"])
        self.assertEqual(result["by"]["visibility"]["hidden_defect"]["images"], 1)

    def test_evaluation_respects_exported_split_policy(self):
        self.sample("dent", specimen_id="part1")
        self.sample("fold", "FOLD", specimen_id="part2")
        export_coco(self.root, ratios=(0, 1, 0))
        predictions = self.predictions([])
        self.assertEqual(evaluate_dataset(self.root, predictions, split="val")["overall"]["images"], 2)
        self.assertEqual(evaluate_dataset(self.root, predictions, split="test")["overall"]["images"], 0)
        self.sample("new", specimen_id="part3")
        with self.assertRaisesRegex(ValueError, "stale"):
            evaluate_dataset(self.root, predictions, split="val")

    def test_invalid_prediction_ids_and_nonfinite_values_are_rejected(self):
        self.sample("dent")
        for invalid in (
            {"image_id": 0, "category_id": 1, "bbox": [10, 5, 20, 10], "score": .9},
            {"image_id": 1, "category_id": 3, "bbox": [10, 5, 20, 10], "score": .9},
            {"image_id": 1, "category_id": 1, "bbox": [10, 5, -20, 10], "score": .9}):
            with self.assertRaises(ValueError):
                evaluate_dataset(self.root, self.predictions([invalid]))

    def test_gallery_is_local_filterable_and_handles_untrusted_text(self):
        self.sample("sample", "FOLD", specimen_id="part", scenario_id="<script>bad()</script>", lighting_profile="raking")
        self.sample("clean", "NONE", specimen_id="clean-part", lighting_profile="raking")
        original_source = (self.root / "images" / "sample.png").read_bytes()
        result = report_dataset(self.root)
        self.assertIn("report/index.html", Path(result["report"]).read_text(encoding="utf-8"))
        page = Path(result["gallery"]).read_text(encoding="utf-8")
        self.assertNotIn("<script>bad()</script>", page)
        self.assertIn("&lt;script&gt;bad()&lt;/script&gt;", page)
        self.assertIn("data-filter=\"lighting\"", page)
        self.assertIn('type="checkbox" id="show-boxes"', page)
        self.assertIn('data-original="thumbs/000001.jpg"', page)
        self.assertIn('data-annotated="thumbs/000001-boxes.jpg"', page)
        self.assertIn('img.src=boxes.checked?img.dataset.annotated:img.dataset.original', page)
        self.assertIn('../images/sample.png', page)
        self.assertIn('../masks/sample.png', page)
        self.assertTrue((self.root / "report" / "contact-sheet.jpg").exists())
        self.assertEqual(result["by"]["lighting"]["raking"]["visible"], 1)
        self.assertEqual(original_source, (self.root / "images" / "sample.png").read_bytes())
        with Image.open(self.root / "report" / "thumbs" / "000001.jpg") as original, Image.open(self.root / "report" / "thumbs" / "000001-boxes.jpg") as annotated:
            self.assertEqual(original.size, annotated.size)
            self.assertIsNotNone(ImageChops.difference(original, annotated).getbbox())
            # The top of the source box is y=5/40*180 plus 30px padding.
            red, green, blue = annotated.getpixel((45, 55))
            self.assertGreater(red, 170)
            self.assertGreater(green, 140)
            self.assertLess(blue, 140)
        with Image.open(self.root / "report" / "thumbs" / "000002.jpg") as original, Image.open(self.root / "report" / "thumbs" / "000002-boxes.jpg") as annotated:
            self.assertIsNone(ImageChops.difference(original, annotated).getbbox())


if __name__ == "__main__":
    unittest.main()
