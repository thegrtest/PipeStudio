# Inspect and test generated images

`dataset_tools.py` works with a Pipe Studio render folder containing `manifest.json`, `images`, `masks`, `labels`, and `metadata`. It uses the project's Python environment and Pillow; Blender is not needed for these analysis steps. It never modifies source inspection images or the rendered image/label files.

From PowerShell in this project folder, replace `exports\challenge` with the generated folder:

```powershell
& .\.venv\Scripts\python.exe dataset_tools.py validate exports\challenge
& .\.venv\Scripts\python.exe dataset_tools.py report exports\challenge
& .\.venv\Scripts\python.exe dataset_tools.py coco exports\challenge
Start-Process exports\challenge\report\index.html
```

Validation checks image dimensions, exact binary masks, visible mask boxes, normalized YOLO coordinates, class IDs, metadata correspondence, unlisted files, and specimen split leakage. An invalid dataset returns a nonzero exit code. Older exports may have antialiased masks and will fail this stricter check; generate a new challenge set with the current renderer.

The report is a local HTML gallery with filters for environment, lighting, defect style, severity, and scenario. Images open at their original size, and each card links to its mask. `report/stats.json` records the counts, including clean images and hidden defects. The contact sheet includes the first 48 images; the gallery includes every sample.

COCO export writes `annotations.coco.json`, separate COCO files and image lists under `splits`, and `dataset.yaml`. Category IDs remain **0 = Fold, 1 = Dent**, matching the existing YOLO labels. These are box annotations; COCO segmentation is deliberately omitted. COCO `image_id` values are one-based positions in the manifest, so keep the manifest order and accompanying COCO file together when producing predictions.

Unassigned specimens go into the **test** split by default. A supplied manifest split takes priority. If a separate synthetic training experiment is wanted, explicitly select grouped proportions:

```powershell
& .\.venv\Scripts\python.exe dataset_tools.py coco exports\challenge --split-ratios 0.7,0.15,0.15
```

Grouping uses `specimen_id` (or `specimen_group`), falling back to `sample_id` and then image path. Keep paired clean/defective views, camera views, and relighting of one specimen under the same specimen ID. Explicit train/test collisions within a specimen are rejected. Hash-based proportions are deterministic but approximate, especially with few groups. The evaluator honors saved group assignments; if the manifest changes, run COCO export again.

## Score detector predictions

Run the detector separately on these images, using the exported COCO IDs, and save a JSON list:

```json
[
  {"image_id": 1, "category_id": 1, "bbox": [120, 220, 60, 45], "score": 0.91}
]
```

Boxes use **pixel x, y, width, height**, with the origin at the top left. An empty list is valid when the detector finds nothing. Unknown image/class IDs, nonfinite coordinates, nonpositive box sizes, and invalid scores are rejected.

```powershell
& .\.venv\Scripts\python.exe dataset_tools.py evaluate exports\challenge predictions.json --confidence 0.25 --iou 0.5 --split test
```

`evaluation.json` reports TP, FP, FN, precision, and recall overall and by scenario, lighting, and visibility. Matching is score ordered, one-to-one, class aware, at one IoU threshold. Duplicate detections count as false positives. This is **not mAP**. Precision or recall is `null` when its denominator is zero. Predictions on clean images and fully hidden defects count as false positives because those images have no visible ground-truth box.

Masks describe exterior support of the procedural deformation, thresholded by the renderer; they do not measure perceptual visibility. A tiny or strongly highlighted defect may be difficult to perceive even when a geometric box exists. These synthetic challenge results cannot establish real-world transfer. Retain an untouched real inspection test set for that assessment, and do not tune the generator or detector against its final outcomes.
