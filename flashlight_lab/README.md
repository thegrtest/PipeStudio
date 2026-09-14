# Flashlight Lab

Standalone Blender / Cycles prototype for the tightly packed flashlight inspection view. This folder does not modify or register with Pipe Studio. All scene geometry, materials, lighting and labels are procedural. The AI concept PNG is a visual target only and is not used as a render background or texture.

## Open and adjust

Double-click **Open Flashlight Lab.cmd**. It opens `output/reference/Flashlight Inspection.blend` and registers a **Flashlight Lab** sidebar in Blender (press **N**). The `.blend` also opens independently without the custom sidebar.

The sidebar controls seed, reference arrangement, clean probability, random axial rotation, image width, Cycles samples and light intensity. Click **Build / update scene** after changing settings. Rebuilding replaces this dedicated scene, including manual edits; save a separate `.blend` before rebuilding edits you want to keep. F12 renders. **Export current image + defect masks** saves an image, per-defect binary masks, YOLO boxes, metadata and an editable `.blend` under a new `output/manual_*` folder. Camera, lights and individual objects can also be edited normally in Blender. The saved `.blend` preserves manual edits; the embedded recipe describes the procedural starting point.

## What is modeled

- Six hollow plastic cylinders, touching side by side, alternating metal bulb ends. Fine ribs, axial grain and sparse cosmetic flecks.
- Separate tarnished metal bulb collars with rolled rims, end caps and unlit front lens discs. The internals are simplified for this overhead view.
- Optional internal battery meshes. Battery absence is stored as latent scene metadata, **not an exterior detection class**. In randomized scenes it is independent of damage; plastic damage can occur with or without a battery.
- Real radial deformation of both shell surfaces for plastic and metal dents. Metal scratches are narrow, shallow geometric grooves. Their support is labeled separately from cosmetic material wear.
- A continuous track under the products, two edge rails, orthographic overhead camera, broad inspection light and grazing fill.

Dimensions are visual estimates, currently diameter 1 and length 3.5625 in illustrative units to match the approved concept. There is no calibrated camera, material scan, impact solver or rigid-body rolling simulation. Random roll samples static inspection poses. It can hide defects on the far side; hidden defects get empty masks and no detection box. Masks describe affected geometry, not a visual acceptance threshold. Contact is an approximate nominal cylindrical envelope; this prototype does not solve contact physics.

## Generate a dataset

From this folder in PowerShell:

```powershell
& '.\Generate Dataset.ps1' -Count 1000 -Seed 5000 -Width 1536 -Samples 96 -RollDegrees 45 -Output '.\output\test_1000'
```

The default launcher produces only 12 images, so accidentally starting it does not launch a large run. `-CleanProbability` is per flashlight, not per image. Use `-CleanProbability 1` for entirely defect-free frames. `-Demo -RollDegrees 0 -Count 1 -Seed 42` produces the reference defect arrangement. Use a new output folder for each job.

For a stopped run, repeat exactly the same arguments with `-Resume`. The renderer checks job settings, generator hash, Blender version and hashes of completed images, masks and labels. Create `stop.flag` in the job folder to stop after the current image; remove that flag before resuming. Concurrent writers are rejected by `render.lock`. After a hard crash, verify the Blender process has ended before manually removing its stale lock. Completed runs can be resumed to verify their existing outputs without rendering again.

Direct Blender command, also useful to create the reference scene on another machine:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' -b --factory-startup --python-exit-code 1 --python '.\flashlight_scene.py' -- --output '.\output\reference' --demo --width 1536 --samples 96
```

## Outputs and model testing

`images/` contains RGB PNGs. `masks/` contains one binary visible-support PNG per procedural defect, including empty masks for hidden defects. `labels/` contains standard YOLO detection boxes. `metadata/` stores the seeded scene recipe, battery state, per-defect visibility and pixel boxes. `manifest.json` indexes completed samples; `job.json` records the generation settings; `status.json` reports progress. The first scene of each batch is saved as `Flashlight Inspection.blend`.

Class IDs are **0 plastic_dent**, **1 metal_dent**, **2 metal_scratch**. These differ from the pipe model's Fold/Dent classes. Multiple scratches on one collar are grouped into one scratch instance. Every sample defaults to the synthetic `test` split. Keep any relighting or re-rendering of the same seed in the same split.

Validate masks, hashes, boxes and labels; create COCO box annotations and an HTML review gallery using the parent project's Python environment:

```powershell
& '..\.venv\Scripts\python.exe' '.\dataset_review.py' '.\output\test_1000'
```

Open `review/index.html`. `annotations.coco.json` uses image IDs starting at 1 and the same zero-based category IDs as YOLO. It contains box annotations, not invented polygon segmentations. `dataset.yaml` describes the YOLO test image directory; point your evaluation tool at the actual dataset folder if it resolves relative paths elsewhere.

No detector weights were supplied or run. These exports are ready for a detector with the three flashlight classes, but the existing pipe detector cannot be assumed to recognize them. Assess synthetic results separately from a held-out real flashlight dataset.

## Implementation boundary

`flashlight_scene.py` exposes `recipe`, `build_scene` and `export_frame` for later integration. `blender_controls.py` is the standalone Blender UI. `dataset_review.py` validates this multi-object format independently of the pipe app. Keep the prototype here until appearance, defect distributions and real camera dimensions are agreed.
