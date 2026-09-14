# Infinite shell conveyor

Open `Infinite shell conveyor.blend` in Blender and play frames 1–144 at 24 fps.
The six-second loop shows the existing six shell variants rolling from left to
right, with brass and plastic ends alternating. The models, print and materials
come from the reference-print workspace. The inspection cameras remain available.

The stream extends beyond the frame. Travel and rotation are linked using the
brass rim radius: one turn travels one circumference. Each loop advances six
shell positions and completes two turns, lining up the next repeated set.
This is a visual rolling rig, without a rigid-body collision simulation.

Select **LOOP CONTROLS - six second conveyor** to change `loop_frames` or
`rolling_radius` in Custom Properties. If changing `loop_frames`, also change
the scene end frame to the same value. Materials and each source shape are
shared across repeated shells, reducing memory use. Source assets are in the
hidden library collection.

The original inspection workspace and dataset files are separate from this scene.

## Capture labeled rolling images

Production defaults are **2400 × 1200**, **192 samples**, a 64-sample adaptive
minimum, and a 0.003 noise threshold. Groove normals are moderately stronger;
the optical filter and bloom are reduced, and plastic highlights are restrained.
Capture motion blur is disabled. Opening the launcher uses the actual scene
lighting in Rendered view, rather than the material-preview studio environment.
The reference match is visual; it is not a calibrated physical camera model.

Double-click **Open Rolling Capture.cmd**, then open the **Rolling Capture** tab
in Blender's right sidebar (N). Choose the frame interval, camera(s), and whether
to save only frames with visible defects or every sampled frame. Click
**Capture rolling images**. A background Blender worker exports the images while
the interactive workspace remains available. **Stop after current image** ends
the worker after its current image and labels finish.
**Resume last capture** continues an interrupted job from its saved image and
skip records, retaining completed files.

The default interval is every 12 frames (two captures per second). **All three
cameras** uses front 45°, rear 45°, and overhead. Capture exposures are sharp:
animation motion blur is disabled in the background worker, so masks refer to
the same instantaneous pose as the RGB image.

Each export contains PNG images, whole-shell/region/defect masks, separate YOLO
datasets, COCO bounding boxes, per-frame metadata, and lossless crops with defect
labels beside the crop images. Shell IDs remain stable through the sequence.
Repeated source meshes receive separate instance IDs. Hidden defects do not get
visible boxes; partial shells remain labeled in source frames and are marked
`edge_truncated`. By default, full-shell crops touching an image edge are excluded.
Dust and body printing remain normal appearance, outside defect labels.

**Randomize defects** is enabled by default. Every incoming shell receives a
distinct seeded recipe. **Passes** controls how many times to capture the selected
frame range with a new population. Geometry is rebuilt once at the beginning of
each pass, then remains unchanged as the shells roll through all sampled frames
and cameras. The track, lighting and rolling motion remain in place.

Defaults are **3 passes**, **4 body dents per group of six**, normal defect
strength, and a **12-degree maximum twist**. Remaining shells use the existing
mixture of clean surfaces, dents, scratches, crimp openings, protruding crimps,
and mild twists. Change **Defect strength** or **Maximum twist** to adjust the
range; zero twist disables twist defects. The four-dent rule describes complete
groups of six shells, not the number of dents visible to the camera at each instant.

**Dirt is currently OFF** in the collection workspace; dust and groove residue
are also set to zero. Production render quality and geometric defects are retained.
The earlier dirty collection was stopped and its files remain in its own folder;
`clean-collection.json` points to the replacement collection.

Enabling **Mix clean and dirty shells** adds independent, seeded normal contamination.
At a 50% heavily dirty setting, each complete group of six contains
three heavily soiled shells, two clean shells, and one lightly dusty shell.
**Heavily dirty fraction** and **Dirt intensity** adjust this mix. Dirt varies
between dry dust, dark grime, and mixed deposits, with irregular patches,
small grains and residue in grooves. It stays attached to the specimen as it
rolls and appears on plastic, brass, and buttons. It does not create defect
labels. Per-shell `normal_appearance` metadata records category, palette, seed,
and strength; defect recipes are independent of these settings. Clean/dirty
appearance variants of the same geometry retain the same training split group.

**New random defects** advances the seed and previews the first pass in the
workspace. Capture uses that same seed for its first pass. Changing the seed
changes the population; keeping it reproduces it. Recipes are saved under
`recipes/` so an interrupted pass can resume with the same defects.

Track IDs stay fixed within a pass and change between passes. Keep all frames
and cameras belonging to a sequence in the same training/validation split;
metadata includes a reproducible `split_group` for each population. Turning
randomization off captures the shells currently saved in the workspace, which
may reuse the original six variants.

## Unattended collection

The saved workspace is prepared for **3,000 accepted images**, across **all three
cameras**, sampled every 12 frames. Click **Start autonomous collection** when
ready. The short preflight dataset is separate from the full collection.

A separate Python supervisor keeps the collection running if the Blender window
is closed. Each pass uses a fresh Blender worker to release render memory. Native
worker exits are retried from the last completed image, using the saved recipe;
three consecutive failures or twelve total failures stop the job for inspection.
The worker timeout is two hours. **Resume last capture** continues a stopped or
failed collection. **Stop after current image** requests a clean stop and finalizes
the completed exports. The image target counts source camera images, not crops.

Each image is committed through `progress.json` only after its metadata, labels,
masks and crops are written. During a run, use those completed records or the
latest manifest instead of treating every file in the images directory as ready.
The compact manifest references full per-image metadata. YOLO datasets are usable
as images complete; aggregate COCO and crop indexes are finalized at the end.
Only visible instances get mask files in this mode; off-screen and occluded
surfaces are not assigned visible labels. The full population remains recorded
in the saved per-pass recipe. A supervisor lock prevents duplicate workers on
the same collection.

Collection stops at the accepted-image target or the maximum pass count. If the
pass limit is reached before the target, status is `exhausted`, not `complete`.

If opening the blend file directly, run the embedded **Enable Rolling Capture.py**
text once from Blender's Text Editor to load the sidebar without rebuilding the scene.

## Mixed dirt and defect video

`dirty-defect-loop/dirty-defects-rolling-loop.mp4` is a six-second seamless
2400 × 1200, 24 fps loop rendered at 192 samples. It shows twelve distinct
specimens: six heavily dirty, four clean, and two lightly dusty. The editable
`dirty-defect-loop/Dirty defect conveyor.blend` is a separate video workspace.
This finite video repeats twelve specimens; production collection uses fresh
seeded populations of unique shells on every pass.

The resumable `verification/run_dirty_video.py` pipeline renders bounded frame
chunks, verifies continuity and the encoded video, and then launches the
authorized 3,000-image collection. Its `collection.json` links to that dataset;
rerunning the pipeline does not launch a second collection when that record exists.
