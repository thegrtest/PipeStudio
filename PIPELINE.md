# Generate a pipe inspection challenge set

Run commands from the `TaperedPipeStudio` project folder. Each output folder is self-contained; source inspection datasets remain unchanged.

```powershell
& .\.venv\Scripts\python.exe generation_plan.py --output exports\my-test --specimens 8 --quality quick --seed 42
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' -b --factory-startup --python-exit-code 1 --python pipeline_runner.py -- --plan exports\my-test\render_plan.json
```

Add `--resume` after the plan path to continue an interrupted generation job. Use the same saved plan. The plan captures the seed, specimen identities, render parameters, scenarios, and splits so the generated set can be inspected and reproduced. Preview quality is for checking the workflow; use the higher quality setting available in `generation_plan.py --help` for final renders.

## Inspect the output

```powershell
& .\.venv\Scripts\python.exe dataset_tools.py validate exports\my-test
& .\.venv\Scripts\python.exe dataset_tools.py report exports\my-test
& .\.venv\Scripts\python.exe dataset_tools.py coco exports\my-test
Start-Process exports\my-test\report\index.html
```

Validation checks binary masks, image sizes, mask-derived boxes, YOLO coordinates/classes, metadata, correspondence, and unlisted files. The local gallery filters by environment, lighting, defect style, severity, and scenario; `report/stats.json` contains visibility counts. COCO export provides box annotations, grouped split image lists, and `dataset.yaml`.

Class IDs are **0 = Fold, 1 = Dent**. COCO image IDs are **one-based manifest positions**; use the accompanying `annotations.coco.json` to map filenames to IDs. Clean and fully hidden defects have no visible annotation. Segmentation is not invented from the boxes.

Unassigned specimens default to `test`. Explicit manifest splits take priority. `specimen_id` keeps clean/defective pairs, camera views, and relighting of one part together. Mixed splits for the same specimen are rejected. For a separately intended synthetic training experiment, `coco --split-ratios 0.7,0.15,0.15` assigns unspecified groups deterministically; do not split related views by image filename.

## Score a detector

No detector is run or downloaded automatically. Run the chosen detector on the generated images, then save its predictions as a JSON list using COCO pixel boxes:

```json
[{"image_id": 1, "category_id": 1, "bbox": [120, 220, 60, 45], "score": 0.91}]
```

```powershell
& .\.venv\Scripts\python.exe dataset_tools.py evaluate exports\my-test predictions.json --confidence 0.25 --iou 0.5 --split test
```

`evaluation.json` contains TP/FP/FN, precision, and recall overall and by scenario, lighting, and visibility. Matching is class aware, score ordered, and one-to-one; duplicate detections count as false positives. This is a fixed-threshold diagnostic, **not mAP**. Undefined precision/recall is `null`. Re-export COCO if the manifest changes so saved split assignments remain current.

Synthetic performance cannot establish performance on real inspection images. Masks describe visible procedural geometry support, not perceptual visibility or acceptance criteria. Keep a separate untouched real inspection test set for assessing transfer. See [DATASET_TOOLS.md](DATASET_TOOLS.md) for detailed formats and edge cases.
