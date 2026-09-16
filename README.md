# Pipe Studio

For tapered brass datasets matched to the inspection cameras, see
[camera-matched generation](DOMAIN_REALISM.md). **Open Camera Matched Pipe
Studio.cmd** opens the Blender controls; **Generate Camera Matched Dataset.cmd**
starts a balanced 3,200-image cycle with resumable exports.

**Fleet Dashboard.cmd** opens a lightweight local monitor for the desktop, DGX
Spark and AGX. See [three-device generation](remote/FLEET.md) for preparing,
starting, stopping and collecting distributed runs.
**Update and Ready Fleet.cmd** sends changed files, checks the current renderer
on all three devices and stages a batch. **Start Fleet Generation.cmd** performs
those checks automatically and then starts production.

The current generator covers eight camera environments with native reference
dimensions, mixed folds/dents/soap/oil defects, localized brass detail, a glare
guard, and slight lighting and camera-softness variation. Synthetic labels use
0 Fold, 1 Dent, 2 Soap stain, and 3 Oil stain. The default domain plan includes
10% good specimens; the optional fleet defects-only setting balances the four
defect classes. See [YOLOX preparation](YOLOX_TRANSFER_PLAN.md) and
[realism references](REALISM_RESOURCES.md).

After configuring the devices in `fleet_nodes.local.json`, start 5,000 unique
specimens **on each device** with:

```powershell
powershell -File remote/Fleet.ps1 -Action Launch -Count 5000 -PerNode -Quality full
```

This starts generation; opening the camera-matched Blender workspace alone does
not. Each saved fleet run carries an immutable renderer snapshot, so editing or
updating this checkout does not alter running jobs.

## Clone and open the current workspace

This repository contains the Python source, shell artwork, reference images,
verification scripts, and editable Blender workspaces. Large `.blend` files and
demo videos use **Git LFS**. Install Git with Git LFS, **Blender 5.1**, and
**Python 3.12** on Windows, then run:

```powershell
git lfs install
git clone https://github.com/thegrtest/PipeStudio.git
cd PipeStudio
git lfs pull
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
& '.\Open Camera Matched Pipe Studio.cmd'
```

The camera-matched launcher opens the current tapered-pipe controls. The optional
rolling workspace remains available through `examples/rolling-shells/Open Rolling
Capture.cmd`; see [rolling capture instructions](examples/rolling-shells/README.md).
The launchers expect Blender at
`C:\Program Files\Blender Foundation\Blender 5.1\blender.exe`; edit that path if
your installation differs. Blender supplies its own `bpy` and NumPy modules;
do not install `bpy` into the project virtual environment.

For the static shell row, use **Open Inspection Workspace.cmd**. To open the
tapered-pipe workspace directly with its controls:

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' '.\examples\brass-v4\Brass Surface V4.blend' --python '.\open_blender_workspace.py'
```

Generated datasets, image sequences, export jobs, local settings, caches,
packaged executables, and older study snapshots remain local and are excluded
from Git. Older documentation links to those generated reports may therefore
be unavailable in a fresh clone. The retained dirty-shell demo is an earlier
optional scene, separate from the current dirt-off capture workspace.

The dataset consolidation tools are `verification/inventory_shell_training.py`
and `prepare_shell_training.py`; run them against locally generated exports.
They do not render new images. For the optional legacy desktop build, install
`requirements-build.txt` and run **Build App.ps1**. Video encoding scripts also
require `ffmpeg` and `ffprobe` on PATH.

### Tests

The root test suite covers settings, geometry, dataset integrity, class/camera
allocation, surface details, optical variation and fleet management. Run it with:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -p 'test_*.py'
```

The Blender workspace now includes **Tapered pipe** and **Flashlight** modes in the **Inspection Studio** sidebar. Open **Open Inspection Workspace.cmd** to use the integrated scene. Each mode retains its own environment and settings while sharing applicable defect, lighting, camera and export controls. See [Blender product modes](INSPECTION_MODES.md). The desktop app remains unchanged.

A Blender workspace for generating images of **open, hollow, tapered brass pipes** with procedural dents and folds. The inspection workspace adds reference-inspired 3D machinery and Cycles rendering. A separate Windows interface is also available.

## Reference inspection workspace (Blender)

Open **Open Inspection Workspace.cmd** or the **Tapered Pipe Studio** desktop shortcut. The latest **Brass Surface V4** scene opens in Blender with its controls registered. In the 3D view, press **N** if needed and select the **Pipe Studio** tab.

- **Upright photo** recreates the supplied screenshot's close framing: dark rear plate, black wheel at left, cylinder and threaded post at right, and bright shoulder reflection.
- **GodsLight** recreates a horizontal mounted pipe with a blurred green/yellow background and pale upper-right reflections, based on 20260819_161848_466_cam5080.jpg.
- **Compare reference in Blender** opens the selected source image in an adjacent Image Editor pane.
- **Pipe shape** includes slight body taper and adjustable rounding at the short shoulder. The presets use relative silhouette proportions estimated from images, with open bores retained.
- **Camera** includes zoom, horizontal/vertical framing and aspect ratio. **Brass surface** controls the finish and olive tint; **Lighting controls** includes separate key/fill/rim lighting, ambient strength and inspection-style highlight clipping.
- **Render preview** or **F12** produces the beauty render. **Export current image + mask** additionally applies the selected sensor noise and saves masks/labels. Sensor noise is applied only during export; it is not shown in the live rendered viewport.

Use **Save controls and scene** to save an editable copy under projects. The latest workspace is examples/brass-v4/Brass Surface V4.blend. Opening that .blend alone retains its geometry/materials; use the command launcher to register the custom controls. A saved copy can be opened with Blender's `--python open_blender_workspace.py` option to restore the controls.

## Version 4: brass surface

The **Brass surface** panel now offers **Reference**, **Drawn**, **Mottled**, and **Satin** finishes. Separate controls adjust dull oxide patches and brighter burnished streaks. Directional reflections are now correctly enabled in Blender 5.1, with uneven machining, fine flecks, shallow surface waviness, brighter cut rims, and a duller bore finish. Finish buttons preserve lights, camera, shape, and defects. Manual light sliders are in **Lighting controls**.

Reference-sized examples and the [before/after comparison](examples/brass-v4/comparison.html) are in examples/brass-v4. See [BRASS_SURFACE.md](BRASS_SURFACE.md) for the reference observations, material model, and checks. New test generations use material version 4; the previous V3 challenge set remains available unchanged.

## Version 3: lighting, finish, and test images

- **Lighting option** offers Matched reference, Broad diffuse, Left grazing, Right grazing, Dim inspection, and Shoulder glare. Switching it preserves the pipe shape, camera, and finish. Its selected name identifies the starting recipe; the sliders remain editable afterward.
- **Defect shape** offers Single, Elongated, Overlapping pair, Oblique, Wrinkled, and Converging. Tilt and secondary-lobe controls vary real wall deformation. **New defect** also varies the style. The pipeline uses body troughs, shoulder dents, and diagonal/axial neck folds observed in the source images.
- **Scuffs and finish marks** adds seeded smudges, sparse dark marks and handling scuffs through material color/roughness. These marks alone receive empty defect labels.
- **Lighting test pipeline** creates both reference rigs by default: 8 specimens per rig × 6 lights = **96 images**, representing **16 specimen identities**. Clean and appearance-marked clean pipes are included. Every view of a specimen shares its geometry, camera and finish. The panel uses the reference recipes and current seed; the separate current-image export uses your manually edited scene.
- **Quick** uses 960-pixel-wide images and 48 samples; **Reference resolution** uses 1600/1936-pixel widths and 192 samples. More specimens repeat the balanced archetypes with new seeds and variations.
- **Open test gallery** shows a filterable local gallery with optional boxes and links to masks. Exports include exact binary masks, YOLO boxes, COCO boxes, metadata, source-feature evidence, grouped test lists and reproducible recipes. All generated starter images are assigned to `test`.

Generate a new set with one PowerShell command, or double-click **Generate Test Set.cmd**:

```powershell
& '.\Generate Test Set.cmd' --specimens 8 --quality quick --seed 42
```

For full quality use `--quality full`. Each run creates a new export folder and opens its gallery when complete. To resume a stopped run:

```powershell
.\.venv\Scripts\python.exe generate_test_set.py --resume exports\YOUR_RUN\render_plan.json
```

Resume verifies the plan, renderer code/build and hashes of every completed output. It refuses to mix edited recipes or outputs. **Stop after current image** completes the current image and mask. See [PIPELINE.md](PIPELINE.md) for detector prediction scoring and [the dataset audit](verification/dataset-study-v3/report.md) for examples and data-quality findings.

The audit covered 11,147 source files (6,318 unique byte hashes), with detailed visual sampling. Existing source COCO validation/test exports repeat original frames, and some source labels are missing, malformed, or conflicting. The original source files remain unchanged. Synthetic challenge results should be evaluated separately from a reviewed real holdout; no detector model has been run by this pipeline.

Version 3 also resolves machining at a coarser material scale so it remains visible in exported inspection images. Small, tilted defects receive extra local mesh samples, preventing jagged crease highlights at quick output resolutions. The radial deformation model retains open bores and paired wall surfaces; very severe overlapping/crumpled metal remains an approximation.

Version 2 adds layered drawn-brass grain, interrupted scratches, uneven roughness, an axial brushing direction that follows the object, small real bevels on cut edges, worn fixture finishes and varied reflections. The lens focuses on the visible wall rather than the empty axis. Final renders use 192 samples; the live viewport uses 64. The editable PS_CameraResponse compositor provides subpixel softness and restrained bright-highlight scatter before export noise. Diagnostic masks bypass that compositor entirely. Fine finish marks are cosmetic material variation; Fold/Dent labels still describe the procedural geometric defect.

Reference-sized Version 2 images and their recipes are in examples/realism-v2. The baseline comparison images and previous saved scene are retained under verification/realism-v2. Focus/blur controls and scene dimensions are illustrative rather than a calibrated physical camera specification.

These environments are manually fitted visual approximations. Fixture shapes, material response, camera and blur have not been physically calibrated. Their 3D surfaces participate in reflections and occlusion; GodsLight uses broad illuminated surfaces to approximate the distant blurred background. Source images and the reference study are retained in references and verification/reference-study.

## Four mixed folders of 500 images

`generate_mixed_dataset.py` creates 2,000 independent specimens with 250 upright and 250 GodsLight images in each folder. Outputs use `batch_01/all/images` and `batch_01/all/labels`, likewise batches 02–04. Good images have empty label files; YOLO classes remain 0 Fold and 1 Dent. Approximately 35% of each defect class is small/shallow. All images use the reference resolutions and 192-sample Cycles settings.

```powershell
.\.venv\Scripts\python.exe generate_mixed_dataset.py --output ..\BrassSynthetic2000 --good 50 --fold 225 --dent 225 --workers 4 --threads 8
```

Counts are **per folder** and must total 500. Choose a new empty output folder for a new run. `progress.json` tracks the workers; `completion.json` records the final verified totals and duplicate checks. To continue an interrupted run, use the same command with `--resume`; the saved plan supplies its original counts and seed. An active run rejects a second generator. The supplied dataset folder also includes **Stop After Current Images.cmd** and **Resume Generation.cmd**.

## Separate Windows interface

Double-click **Open Standalone App.cmd** in this folder or **dist\Pipe Studio\Pipe Studio.exe** for the earlier standalone interface. Its packaged controls cover the original studio workflow; use Blender for the new reference scenes and shape controls. The entire TaperedPipeStudio folder must stay together. The packaged app includes its own Python interface runtime; Blender must remain installed.

## First image

1. Choose **Clean**, **Dent**, or **Fold**.
2. Adjust the defect controls. **Bring defect to camera** moves it onto the visible side; **Generate another defect** changes the random seed.
3. Choose a look: **Soft studio**, **Inspection light**, **Grazing light**, or **Brushed brass**.
4. The preview updates after you stop changing a control. **Update preview**, **F5**, or **Ctrl+Enter** also renders it.
5. Use **Export current image** in the Export tab to save the image, mask and labels at your chosen resolution and quality.

Drag the preview to change camera yaw/elevation; it renders when you release. This is a ray-traced image preview, so camera movement is not a continuous real-time 3D view. Previews use 960-pixel width and 20 samples for responsiveness; final exports use the selected quality.

## Controls

| Tab or tool | Purpose |
|---|---|
| Defect | Type, position along/around the pipe, depth, length, arc, irregularity and seed |
| Light | Lighting preset, brass roughness, surface wear, brushing, light angle/power, reflection softness, color cast, exposure and sensor noise |
| Pipe | Length, radius, taper, wall thickness, camera and depth of field |
| Export | Output folder, resolution, samples, current image or randomized batch |
| Mask / box toggles | Overlay the visible affected surface and its bounding box |
| Compare reference | Load a local reference photo and display it beside the render |
| Save setup / Load setup | Save and restore controls as a JSON recipe |

Controls are saved on exit. Dimensions use relative scene units. Both ends have open bores. The taper start must be below its end. A defect can be hidden behind the pipe; bringing it toward the camera makes it easier to inspect.

## Dataset export

Use **Generate batch** to vary defect type, location, shape, surface finish, exposure, and lighting. Set the clean-image probability and whether defects should remain near the camera. The seed makes the scene recipe reproducible, though exact pixel results may differ across renderer versions or hardware.

Each export creates its own output directory. Progress appears in the footer. **Stop after current image** finishes the current image and mask before stopping. Closing the app also requests a graceful stop; its hidden renderer may take a moment to finish that frame. Previews queued during export resume afterward.

| Output | Content |
|---|---|
| images/*.png | RGB renders in the chosen environment's aspect ratio |
| masks/*.png | Visible exterior surface affected by the geometric defect |
| labels/*.txt | YOLO bounding boxes: **0 = Fold, 1 = Dent** |
| metadata/*.json | Parameters, dimensions, visible mask pixels and bounding box |
| classes.txt | Class names in label order |
| manifest.json | Completed sample index |
| job.json | Requested settings, seed and batch recipe |
| status.json | Completion, progress or error details |
| last_scene.blend | The final scene for further inspection in Blender |

Clean samples and defects completely hidden from view have empty labels. Masks mark the projected exterior region whose displacement exceeds 3% of the nominal peak defect depth. They describe geometric support, not the exact region a human inspector would see in reflected light. Depth of field and sensor noise affect beauty images; diagnostic masks remain sharp and noiseless.

## Realism and reference matching

The renderer uses physically based metallic shading, area-light reflections, perspective projection, surface grain, finish variation, shadows, and optional depth of field and sensor noise. Exports above 1200 pixels use a denser mesh. Grazing and narrow inspection lights can make small surface changes easier to see.

Use Compare reference to match the view, taper, framing, finish and reflections manually. The supplied datasets provide reference photos and defect labels; they do not include measured 3D geometry, calibrated cameras or light measurements. The app therefore generates an adjustable approximation, not an automatically calibrated digital twin. Dents and folds are procedural visual deformations, not a mechanical forming simulation. One localized defect is generated per pipe.

## Troubleshooting and development

- If the renderer stops, use **Update preview** to restart it.
- Interface errors are recorded in application.log. desktop_runtime.json identifies the active session; its .cache/desktop-sessions/<session>/worker.log contains renderer details.
- **Open Blender Workspace.cmd** opens the current native inspection workspace.
- Source interface: desktop_app.py. Settings: app_model.py. Background worker: desktop_worker.py. Geometry: geometry.py. Renderer: pipe_studio.py.
- To rebuild: create .venv with Python 3.12, install requirements-build.txt, then run Build App.ps1.
- Run unit checks with `.venv\Scripts\python.exe -m unittest test_geometry test_app_model`.
- Run the desktop integration check with `dist\Pipe Studio\Pipe Studio.exe --ui-test` in an interactive Windows desktop session. It renders previews, checks masks and exports two images, saves verification screenshots, then closes.

Technical references: [Blender Python API](https://docs.blender.org/api/5.1/), [Principled BSDF](https://docs.blender.org/manual/en/4.0/render/shader_nodes/shader/principled.html), [PyInstaller usage](https://www.pyinstaller.org/en/stable/usage.html).
