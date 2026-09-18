# Inert assembly inspection track

Open `Open Assembly Track Studio.cmd` for the native Blender editor. The
**Assembly Studio** sidebar changes the specimen seed, primary defect,
position/roll, bar brightness and exposure. F12 renders the camera. Dataset
generation runs in a separate background Blender process. The existing fleet
and its eight upstream inspection environments are independent of this scene.
Brightness and exposure sliders control the interactive preview. Balanced
exports use the seeded, restrained lighting variation recorded in each recipe.

The elevated **CAMERA_MATCHED** scene is the default for new launches. Choose **Scene version: Original** and
**Current lighting** to keep the first version, or **Refined camera environment**
for the revised camera framing, rounded copper end and brass end bead, warmer
neck/oxide finish, worn upper rail and softer foreground guide. Changing scene
version requires **Build / randomize specimen**; lighting switches immediately.

Version 4 raises the inferred camera to about 36 degrees above the track and
fits the native assembly to approximately 550 pixels across near (872, 775).
The two verified empty machine frames under `assets/assembly_cam3936` supply
the camera background; all parts, defects and contact shadows are rendered
in Blender. `provenance.json` records their source paths, visual review and
hashes. These are hybrid images, not fully synthetic environments. F12 shows
the final composite; the modeling viewport retains editable procedural fixtures.
`--look REFINED` selects the entirely procedural scene without the camera plate.

The new view follows the diagonal image corridor inferred from the references.
It uses projected placement and nominal roll, not measured guide-contact
kinematics; `guide_clearance` is null and the placement method and actual world
position are recorded. Foreground sensor noise and scaled optical softness do
not re-blur or re-noise the photographed background. Exposure compensation
preserves the background while varying the rendered part's illumination.
Balanced light bands vary across the drawn finish and have unequal intensities;
FOUR_LINES keeps the deliberately uniform four-bar option.

For remote generation, `remote/assembly_fleet.py launch --nodes spark,agx --count
5000` assigns 5,000 images per remote device and excludes the desktop. See
`remote/FLEET.md` for status, pause, resume and retrieval commands. The fleet
uses the same assembly exporter, immutable render snapshots and separate label
namespaces, with bounded render chunks and automatic retry after interruptions.

Only two empty background captures are available. Background assignment is
seed-hashed so the alternating dent/fold schedule does not determine the plate.
This matches one camera station, not arbitrary future backgrounds. Review the
native real/old/new comparisons in `verification/assembly_topdown_v4_matched/index.html`.
Version 5 adds a local brass-body finish fit, reviewed in
`verification/assembly_surface_v5_final/index.html`. The same 160 × 80 native
pixel patch is shown for the real camera, v4 and v5. Balanced lighting places
the four bands to match the reference, with a stronger upper reflection.
The oxide fill is excluded from glossy rays to remove an unintended fifth
reflection. The proxy floor no longer tints the shaded brass green, and the
reflection bars are linked to the assemblies so they do not cast exaggerated
shadows on the background proxy. Ambient lighting retains contact shadows.
`assembly_finish.py` supplies seeded short-scale grain, warm oxide and restrained
roughness variation. No real part pixels are used for material textures.
The finish version and seed are recorded in `surface_finish` metadata; the
module participates in resume fingerprints. Original/refined looks remain
unchanged. This pass targets the brass body; copper/neck calibration is separate.

Finish differences remain visible; do not treat whole-frame similarity from a
reused background as evidence of model transfer. Evaluate on held-out real parts
and another capture session before estimating production rejection performance.

Version 3 gives newly planned refined specimens a small-dent emphasis: roughly
65% of dent instances are small circular bowls, 20% broader shallow bowls, and
15% the larger varied dent families. This changes dent shape/size, not the
primary class balance. Folds and mixed defects remain available. Smooth
compact displacement replaces raised crater rims on the circular families;
diameter and depth vary independently. Local mesh refinement resolves these
features and the same displacement field supplies each label mask. Circular
means round in the surface's physical tangent coordinates; camera perspective
can make it appear elliptical. Very shallow dents can be hard to see; labels
represent geometric support, not guaranteed human/model detectability.

The revised fixtures have a curved rail face with more localized gold
reflections, rounded nylon strip ends, quiet broad track variation, and less
surface bump. The eight native labeled examples are in
`verification/assembly_small_dents_v3_final/index.html`.

An already-running renderer keeps its saved plan and loaded code. The completed
September 16 dent/fold batch retains its `renderer_snapshot` and **Resume Cycle.cmd**
in its output folder. New cycles use version 5; the completed earlier previews
and datasets stay available.

| Lighting preset | Appearance | CLI value |
|---|---|---|
| Current lighting | Preserves the original four emitter positions and surface response | `CURRENT` |
| Four crisp reflection lines | Four separated, narrow real reflections; equal bar powers | `FOUR_LINES` |
| Balanced / in between | Broader, softer bands with restrained intensity variation | `BALANCED` |

The two new presets also constrain material roughness to control reflection
width. Underlying finish maps, defect geometry and seed stay the same when
switching. Reflections bend with defects; they are not painted stripes. The
thin contact guide uses a transmitting approximation to avoid a reflected
duplicate absent from the references; the foreground acrylic remains visible.
The earlier preview remains in `verification/assembly_track`. Open
`verification/assembly_realism_v2_final/index.html` for the paired native-size
comparison with real reference photos and toggled component/defect boxes.

The camera outputs **1920 × 1200**, matching the supplied cam3936 originals.
`--scale 2` renders 3840 × 2400 with the same framing and scaled optical blur.
The geometry is an inert exterior visualization with inferred proportions,
not a mechanical CAD model. The perspective camera includes a second unique
assembly farther along the track, which can be larger or partially cropped.

```powershell
# Small review: all five primary conditions, three rolling views each.
.\.venv\Scripts\python.exe assembly_generate.py --output exports\assembly_review --count 15

# Four crisp reflections; use BALANCED for softer bands.
.\.venv\Scripts\python.exe assembly_generate.py --output exports\assembly_four_lines --count 15 --look REFINED --lighting FOUR_LINES

# Preserve the first scene and lighting.
.\.venv\Scripts\python.exe assembly_generate.py --output exports\assembly_original --count 15 --look ORIGINAL --lighting CURRENT

# 1,200 images: complete balanced blocks, including good assemblies.
.\.venv\Scripts\python.exe assembly_generate.py --output exports\assembly_1200 --count 1200 --seed 300000

# Dent/fold focus: 45% dent, 45% fold, 10% good; mixed defects use only these two.
.\.venv\Scripts\python.exe assembly_generate.py --output exports\assembly_dents_folds --count 1200 --seed 300000 --defect-set DENTS_FOLDS

# Resume the same plan after a pause or interruption; settings must match.
.\.venv\Scripts\python.exe assembly_generate.py --output exports\assembly_1200 --count 1200 --seed 300000 --resume

# Pause only this assembly export after its current image/labels commit.
New-Item -ItemType File exports\assembly_1200\STOP -Force
```

Each full 120-frame block has 10% primary good and 22.5% each dent, ding,
scratch and deformity. Mixed defects and the companion assembly can add
annotations; defects hidden by roll or clipping are not labeled as visible.
Good primary frames also have a good companion. The 15-frame review is a
coverage sample, rather than a full ratio block. Clean finish and minor
cosmetic handling marks occur independently of the diagnostic condition.
The `DENTS_FOLDS` selection balances over each 60-frame block and keeps the
existing label IDs: dent = 0; folds = 3 (`deformity`). No diagnostic ding or
scratch is introduced on either assembly in this mode. Cosmetic finish marks
remain. Supply the same `--defect-set` when resuming.

## Exports

| Dataset | Images | YOLO labels | Class IDs |
|---|---|---|---|
| Defect detection | `all/images` | `all/labels` | 0 dent, 1 ding, 2 scratch, 3 deformity |
| Part tracking | `tracking/all/images` | `tracking/all/labels` | 0 shell, 1 ferrule |

Each dataset includes its own `classes.txt`, `dataset.yaml`, `train.txt` and
`val.txt`. The two image collections intentionally contain the same captures;
hard links save storage where supported. Do not combine the two label
namespaces. Do not merge these new defect IDs directly into the upstream
fold/dent/soap/oil dataset without an explicit mapping.

`metadata/*.json` records both assemblies, poses, source recipes, visible
support, component/defect track IDs, hidden defects, clipping checks and
image/label SHA-256 hashes. Both assemblies and all three adjacent views stay
in one `split_group`; the exporter keeps groups out of both splits. A tiny
preview is insufficient to measure class-wise model performance. A one-group
run has no validation images rather than reusing training images as validation.

`masks` contains separate component and diagnostic support masks. Opaque
geometry occludes annotations. The clear plate is transparent for geometric
labels, so its reflection ghosts are not mistaken for additional objects.
Blur and sensor noise affect RGB only. Labels include the visible portion of
a cropped component, and no box for a completely out-of-frame component.
Pixel-size annotations are retained and their visible areas are recorded.

`status.json`, `summary.json` and `index.html` provide progress, counts and a
toggleable label review. Completion requires all pairs, independent beauty
hashes, and a complete saved plan. An OS file lock prevents two writers to the
same output. Resume rechecks committed hashes and refuses changed renderer
sources or different settings. A failed export can be resumed after fixing an
external problem; a renderer change requires a new output directory.

## Rendering and limits

The shell reuses `brass_material`, `brass_realism`, `brass_spectrum` and
`brass_microdetail`. This station has a more burnished finish, with four actual
area emitters. Reflection lines react to mesh dents and thin scratch grooves.
Deformities retain the existing buckle, wrinkle and axial pinch families.
Object-local finish stays fixed while rolling; exposure, light balance,
fine camera noise and mild optical blur vary within restrained ranges.

The supplied images constrain framing, proportions, color and fixture lines.
Fixture depths, camera extrinsics, finish response and light placement are
inferred and editable. Rolling uses the nominal radius and track contact,
not a rigid-body contact simulation of a deformed part. The refined preview
improves the match but is not calibrated radiometry or proven
transfer to real camera data. Judge the preview against the original cam3936
images and evaluate a held-out real sequence before relying on rejection rates.
