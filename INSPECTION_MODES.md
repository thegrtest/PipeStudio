# Blender inspection workspace: pipe and flashlight

The newest **Brass button track** environment models the updated exterior and adds two opposing 45° cameras, one overhead camera, and separate top/body/Brass Face/Plastic Face annotations. See [Brass button track](BUTTON_TRACK.md). The launcher now opens this latest scene; all earlier environment buttons remain available.

Open **Open Inspection Workspace.cmd**, **Open Blender Workspace.cmd**, or **Open Pipe Studio.cmd**. These now select `examples/inspection-modes/Inspection Studio.blend`. In Blender's 3D View press **N** and select **Inspection Studio**. The product selector at the top switches between **Tapered pipe** and **Flashlight**. The desktop app is unchanged.

Both products share defect position, depth, length, angular footprint, rotation, irregularity, seed, roughness, lighting, exposure, framing, resolution, samples, mask display and background exports. Each product remembers its own control values when switching. Save controls and scene stores the selected mode and both remembered configurations in an editable `.blend`; open a saved copy with `--python open_blender_workspace.py` to register its controls. Opening a `.blend` by itself retains the objects and render settings but does not register the sidebar.

## Tapered pipe

Studio, Upright photo and GodsLight environments are retained, including the existing hollow brass geometry, finish controls and lighting test pipeline. Supported defect classes remain Fold (0) and Dent (1).

## Flashlight

Overhead track and Grazing track use a tightly packed row of alternating flashlights. The grazing setup lowers and narrows the side inspection light. Both are fully modeled scenes. The camera stays overhead; zoom, horizontal/vertical framing and aspect ratio are adjustable.

**Product geometry** controls row count, axial roll and seeded battery-presence probability. The battery is a simplified internal mesh, not an exterior label. The model is an illustrative visual approximation, not a calibrated impact or rolling simulation.

**Surface defect** supports Clean, Dent and Scratch. With **Selected flashlight**, choose the row index (0 is the leftmost) and the plastic or metal housing. Scratch selects the metal housing automatically. The shared size and position controls act on that housing. With **Mixed row**, a repeating mix of clean products, plastic dents, metal scratches and metal dents shares the selected severity and footprint; the seed varies local placement and surface details. Clean overrides either arrangement. Zero depth produces no defect labels.

**Bring defect to front** accounts for axial roll. Rotating a defect out of view results in an empty support mask and no bounding box. Appearance-only grain and tarnish do not receive defect labels. Scratch groups on a collar share one instance label.

**Surface finish** controls material roughness and grain. Lighting and camera controls that do not apply to the flashlight setup are hidden.

## Export

Use **Export current image + masks** or **Export and batch → Generate randomized batch**. The existing Blender background worker renders snapshots of the current controls. Editing or switching modes while a batch runs does not change that batch. **Stop after current image** uses the same cancellation mechanism for both products. Clean probability is per image, including for flashlight rows.

Flashlight outputs include:

- `images/`: RGB PNGs.
- `masks/`: per-defect binary visible-support masks and one combined mask per image.
- `labels/`: YOLO boxes, with 0 plastic_dent, 1 metal_dent, 2 metal_scratch.
- `metadata/`: shared control settings, seeded flashlight recipe, battery states, visible areas and boxes.
- `manifest.json`, `classes.txt`, `annotations.coco.json`, `dataset.yaml` and `last_scene.blend`.

Pipe class IDs and its existing dataset format stay unchanged. Do not combine the two products' class IDs without an explicit mapping. Flashlight masks describe the visible affected mesh faces, not perceptual detectability or an acceptance threshold.

The separate pipe lighting-test panel appears only in pipe mode. Flashlight batches use the selected track environment and current controls. To validate a flashlight export and create a review gallery, run:

```powershell
& '.\.venv\Scripts\python.exe' flashlight_lab\dataset_review.py 'PATH_TO_FLASHLIGHT_EXPORT'
```

All exports are synthetic evaluation material; no trained detector is automatically loaded or run.

## Implementation and checks

`pipe_studio.py` owns the shared settings, operators and job dispatch. `workspace_ui.py` displays mode-appropriate panels. `flashlight_integration.py` connects the standalone procedural scene builder to shared controls and exports. `product_modes.py` supplies mode defaults; `app_model.py` validates the renderer's settings. No desktop UI or packaged executable was changed.

Run `test_product_modes.py` for validation checks and `verification/verify_product_modes.py` with Blender for real render, mode-switch, mask-isolation and asynchronous batch checks. The updated workspace is built from the existing Brass Surface V4 `.blend` so its pipe reference setup is retained.

Verified on Blender 5.1.2 / RTX 5080: 62 regression tests passed; actual pipe → flashlight → pipe renders retained the pipe's defect box; all three flashlight classes, clean images, hidden defects, mask restoration and a two-image background batch passed. Exported masks and YOLO boxes passed pixel-level validation. Reloading the distributed workspace retained the original MACHINE pipe environment and both modes' settings. Grazing-light placement, reduced row count, selected-index clamping and zero-depth labels were also checked. `verification/run_mode_tests.py` runs the regression suite with workspace-owned temporary directories for the Windows sandbox.
