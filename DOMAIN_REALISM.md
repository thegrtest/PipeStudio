# Camera-matched tapered brass generation

**Latest candidate:** new CLI cycles now default to the `yolox` sampling profile:
40% mixed among defective images, bounded capture variation, and per-instance
input-size diagnostics. `--profile reference` retains the 25% mixed recipe
documented below. See [YOLOX_TRANSFER_PLAN.md](YOLOX_TRANSFER_PLAN.md) for the
current data audit, prepared cycle, controlled training experiments and saved
prediction scorer. Existing running fleet snapshots are unchanged.

The September 14 revision responds to failures in the supplied August camera
frames and their saved YOLOX prediction overlays. It adds short axial pinched
folds, camera-specific illumination and independently labeled mixed defects.
The current refinement also fits smooth distant-background radiance from
development photographs. The foreground brass, defects and nearby fixtures
remain rendered geometry. No real image files are added to the exported
training dataset; the existing synthetic-only `thegreatawkaning` bundle is
unchanged.

## What changed

The previous all-environment generator forced every rig to dark surroundings
and at least 1500 W key power. This erased the differences between the bright
cam2534/cam5080 captures and the dark cam7650 view. Three explicit horizontal
camera profiles now keep their framing, holder side, background, color cast,
focus and illumination. The original upright machine, square upright,
foreground, inverted and studio setups remain available: eight setups total.

`AXIAL_PINCH` adds a tapered axial seam and unequal lip. Secondary strength
morphs a narrow slit into a wider pocket; all six previous styles remain.
Drawing fields are seeded per specimen, with shallower machining normals.
Clean, handled and dirty finishes occur independently of the defect class.

The second September 14 refinement inventories 4,417 JPGs across seven
BrassModel11 sessions and examines real fold labels alongside saved evaluation
overlays. It adds these changes:

- Finer axial alloy variation that remains visible in polished areas, a thin
  tarnish film, sparse oxidation and shallower surface normals. The native
  Blender controls and dataset exporter use the same material function.
- Revised camera framing and illumination, separate reflective fixture lights,
  recessed bores, fixture waviness and camera-specific channel noise. Sensor
  noise is applied to the beauty image only, after the optical response.
- Elevated fill lighting fitted against vertical body-brightness profiles,
  replacing the overly central reflection band. Light azimuth now changes
  actual key/fill placement after the camera-specific setup is applied, so
  the planned mild and grazing variations reach the renderer.
- August 19/20 acquisition choices, including the lower cam5080 placement in
  August 20. Session selection uses a separate seeded stream, independent of
  labels, with 30% August 20 among the three named cameras.
- 42% of the axial-pinch placements near the mouth rim and 20% of primary folds
  near the visible silhouette. The other fold families and balanced mixed
  defects remain available.

`reference_environment_fields.json` records fits from six development frames
per camera per session: 36 photographs total. The fitter excludes pipe and
mount regions. Each camera/session uses 280 smooth Gaussian basis functions;
the renderer evaluates this field into a small floating-point lookup for the
distant plane. Raw photo pixels, real foreground parts and their defects are
not used as render backplates. This view-dependent approximation does not
reconstruct distant machinery geometry or arbitrary-view parallax. Reference
paths and fitting errors are recorded for auditability. Do not use these same
acquisition sessions as an independent holdout after tuning against them.

The inventory also contains older April/May setups, different part shapes and
blank captures. Those configurations have not all been reconstructed. The
current coverage is the three August cameras and the existing five setups,
not every camera condition present in BrassModel11.

The supplied evaluation overlays show small folds missed or called dents and
machine slots/glints called defects. In the local label audit, median fold
short-side size at a 640-pixel input was 14.21 px real versus 30.40 px in the
older synthetic bundle. The new population emphasizes small, elongated folds
and includes clean images with reflective fixture hardware. Those geometric
and visual improvements do not establish detector transfer accuracy.

## Generate and resume

Double-click **Generate Camera Matched Dataset.cmd**, or use:

```powershell
python generate_domain_dataset.py --output ..\BrassDomainCycle_New --count 3200
python generate_domain_dataset.py --output ..\BrassDomainCycle_New --resume
```

An 80-image review batch (10 per setup) can be generated with:

```powershell
python generate_domain_dataset.py --output ..\BrassDomainPilot_New --preview --quality quick
```

Full runs accept multiples of 320 for exact allocation across eight setups.
At 3200 images: 320 good, 720 each with a primary Fold/Dent/Soap/Oil defect.
25% of defective images receive a second distinct defect class; total instance
counts are 900 per defect class. Primary image counts and instance counts are
reported separately. 45% of instances are small, 40% medium and 15% large;
60% of primary folds use the new pinch family. Lighting is 70% mild variation,
20% broader variation and 10% low-light or grazing cases.

Outputs are `all/images`, `all/labels`, per-instance `all/masks`, and recipes
in `all/metadata`. Class IDs: 0 Fold, 1 Dent, 2 Soap stain, 3 Oil stain
(including acid-like discoloration). Clean images have explicit empty labels.
Localized stains receive labels; ordinary grain/oxidation are finish variation.

Workers render to temporary storage, publish labels before RGB, and commit
each sample to the manifest last. Bounded retries cover transient file locks.
Resume checks the saved plan, renderer fingerprints and committed file hashes;
use a new folder after changing the renderer. The output folder's **Stop After
Current Image.cmd** sets a cooperative stop flag. The launcher does not train a
model or modify an existing dataset.

Full quality uses 128 Cycles samples at the reference's dimensions. Quick uses
64 samples and caps the longest side at 960 pixels; it never enlarges a smaller
reference. Camera framing, optical blur and defect pixel scale use the same
reference frame:

| Setup | Full image dimensions | Reference |
| --- | --- | --- |
| CAM2534, CAM5080, CAM7650 | 1936 × 1216 | Supplied GodsLight JPGs |
| UPRIGHT, FOREGROUND, INVERTED | 640 × 640 | September square captures |
| MACHINE | 795 × 638 | Older upright screenshot; proxy, not raw sensor calibration |
| STUDIO | 1936 × 1216 | Comparison setup; proxy without a real camera reference |

Plans record the reference source, expected dimensions and calibration caveats.
Matching dimensions is not a claim of measured lens/sensor calibration. Render
metadata includes approximate, uncropped mesh bounds for checking the pipe's
size and placement in pixels; these do not account for fixture occlusion or
bevel modifiers. Each geometric/stain instance gets a separate
occlusion-aware mask and box on the same deformed specimen. Invisible instances
fail the sample rather than silently becoming clean training images.

## Review and evaluation

```powershell
python domain_review.py ..\BrassDomainCycle_New
```

This validates file pairs/hashes, image uniqueness, instance masks and boxes,
and expected plans; it creates `index.html`, `contact_sheet.png` and
`validation.json`. The review pilot is intentionally a coverage set, not the
production class distribution.

The initial September 14 verification completed an 80-image coverage pilot and
a 16-image native-resolution check. The second refinement completed another
80-image native-resolution check with 88 independently labeled defects: all
image/label pairs, masks, dimensions and hashes passed. Its median fold short
side at a 640-pixel input was 15.37 px, versus 14.21 px in the real-label audit
and 30.40 px in the older synthetic bundle. This small coverage set is not a
production distribution or a detector accuracy test. All 80 image byte hashes
were distinct; this does not rule out perceptual near-duplicates. The targeted
source suite passed 102 tests.

The final material/fixture pass has its own review batch and source fingerprint:
`../BrassRealismV2_Validated80_20260914/index.html`. The interactive reference/before/
refined comparison is `verification/realism_v2/index.html`; it includes native
pixel viewing, body crops, saved fold prediction crops and selected-region
color measurements. Generated reports remain local and are not in Git.
The review passes deliberately reuse the same 80 specimen seeds for controlled
comparisons. Do not merge the intermediate passes into training or count them
as new independent specimens. The unstarted 3,200-image production plan in
`../BrassRealismV2_Ready_20260914` uses a separate seed range and the final
renderer fingerprint; its **Resume Generation.cmd** starts that prepared plan.

The images are closer in several visible characteristics but remain
distinguishable. Highlight shape, uneven surface markings, fixture machining
and lens response still differ. Lower error on a fitted background or selected
color patches does not prove perceptual equivalence or better detector transfer.

The copied September 14 evaluation folder contains annotated images but no
checkpoint fingerprints or numerical evaluation history. It supports the
observed failure examples, not a verified worsening-real-across-epochs claim.
The real labels contain Fold/Dent only, while the synthetic model also predicts
Soap/Oil; use class-aware metrics and review stain coverage before counting all
unlabeled marks as errors. Fixture detections can be tracked separately.

Use these inspected frames for development; reserve other acquisition sessions
or complete part sequences as a real holdout. Compare checkpoint hashes with
fixed confidence/NMS/input settings, Fold/Dent recall by camera and size,
fold-to-dent confusion, and fixture false positives. Training and fresh detector
inference are separate from this generator revision.
# Defect glare protection (September 14)

New camera-matched and fleet renderer releases apply `glare_guard.py` before
committing an image. The check measures final PNG display values inside every
visible defect mask, nearby pipe surface, and a separate pipe silhouette. Bright
background fixtures are excluded. Small metallic glints and non-clipped pale
soap residue remain allowed. Near-clipped white/yellow coverage is limited to
10% of a defect, 22% of its local context, and 3.5% of the visible pipe.

Failed candidates reuse their exact specimen, camera, resolution, and masks,
with a bounded sequence of lower direct-light power, gentler fill reductions,
and small exposure corrections. Only RGB is rerendered. Every attempt and the
accepted light powers/exposure are saved under `glare_guard` in metadata; the
`parameters` field still records the original planned settings. An unresolved
failure raises before publishing rather than silently dropping an annotation
or changing a class. Dataset review independently rechecks the actual PNG.

This is a clipping heuristic, not proof of defect detectability or YOLO transfer.
Active fleet releases are immutable and were not patched or stopped. The fix
ships with the next newly packaged cycle; resuming an old cycle keeps its old
renderer. Existing images and training datasets are not retroactively altered.
Regression previews: `verification/glare_guard/index.html`.

## Shared forming and fixture finish (September 19)

`inspection-forming-detail-6` adds a faint, physically scaled axial draw field,
unequal interrupted draw tracks, circumferential neck rubs and patchy shoulder
burnishing to the existing sparse handling marks. The taper dimensions locate
the neck/shoulder treatment. Clean specimens still have manufacturing texture;
handling density continues to follow the clean/dirty controls. All fields are
seeded independently of class, camera and light. They affect reflectance,
roughness and shallow shading normals, not geometry or diagnostic masks.

The first comparison still looked cloudy, so a second pass lengthened and
softened individual track ends and added a weak continuous drawing field.
The same material path serves the eight tapered-pipe setups and the assembly
brass. Existing camera-specific optics, native dimensions, class allocations
and the assembly's separate appearance adjustments remain in use.

Machine fixtures now include sparse interrupted wipe traces and contact patches
in object-space scene units. Their grain no longer depends solely on stretching
a texture across each object's bounding box. Per-object offsets prevent adjacent
pieces from sharing the same marks. This shared fixture shader applies to the
machine and GodsLight rigs; the studio has no such fixture. The photo-backed
assembly environment keeps its separate construction.

Review: `verification/finish_20260919/index.html`, built with
`verification/report_finish_refinement.py`. It includes real/before/refined
body, shoulder/rim and fixture crops, and 21 frames across all eight setups.
All 21 exports passed dataset validation and glare checks. All compared labels
and masks were identical before/after; three additional matched-camera frames
also passed. Two lighting controls retained the same surface detail and labels.
Fourteen targeted Python checks and the Blender material refresh/class
independence checks passed. A native assembly frame and its camera/compositor
regression checks cover the shared material dependency.

These are development comparisons of different physical specimens, not a
measured detector-transfer improvement or an indistinguishability result.
Holder shape, highlight distribution and individual-part color still differ
from the real camera images. Review files must not enter production training
or holdout sets. Production datasets and paused fleet snapshots were not changed;
new jobs must package the updated source, while old resumable jobs retain theirs.

## Inverted-camera body defect gap (September 23)

Fleet profile `body-gap` is deliberately restricted to the INVERTED machine
camera at its native 640 x 640 resolution. It does not distribute examples over
the other seven environments. The development references are checkpoint
comparison screenshots: their predicted Fold boxes/confidences are not ground
truth, and no screenshot pixels enter generated training images.

The 3,200-image recipe has 1,600 Fold and 1,600 Dent primary specimens. Forty
percent contain mixed classes, including 10% of all specimens with a third
instance. Total instances are 2,400 of each class, with 45% small, 40% medium
and 15% large. Seventy percent of primary defects target the observed darker
body above the shoulder: shallow round/oval dents or a rounded transverse
`BODY_BUCKLE` fold. The remaining 30% retain existing geometry families. Labels
and masks follow actual deformation and visibility; unsupported hidden defects
fail export. Strong shoulder reflections remain context, while the existing
defect glare guard still applies.

Clean/handled/dirty finish remains 30/35/35, lighting 70/20/10 mild/stronger/stress,
and the existing mild camera-softness distribution is retained. These nuisance
distributions are balanced independently within each primary class. Sixty
percent use a slightly darker body fill. The second recipe iteration reduces
burnished-track strength and increases roughness after the first 18 previews
still looked too streaked. All changes to sampling are confined to this profile.
Specimens receive unique seeds and an 80/20 train/validation assignment; preview
seeds and outputs are separate. This is a targeted transfer experiment, not a
claim of indistinguishability or measured detector improvement.

Dispatch example (total count shared across the two remote devices):

```powershell
.\.venv\Scripts\python.exe remote/fleet.py start --nodes spark,agx --profile body-gap --count 3200 --quality full --seed 923283000
```

`spark` is the configured DGX host. Desktop is excluded. Run a smoke check with
a different seed before production when changing the renderer; `--smoke`
renders both classes on each selected device. Completed outputs and resumable
progress remain inside each node's immutable fleet job, under `all/images`
and `all/labels` with metadata and masks alongside them. Use the saved run's
`status`, `stop`, `resume`, and `fetch` actions rather than creating a duplicate
run to recover interrupted work.

## Dried soap film from the August 12/13 references

`soap_residue.py` adds three flat material deposits for `SOAP_STAIN` (YOLO class
2): faint round films, irregular dried islands, and connected/coalesced residue.
These approximate the pale yellow/cream spots in the supplied TestDataset
camera frames. Seeded outlines have uneven lobes and softly varying thickness;
the underlying brass shader and its fine normals remain visible through the
film. No photograph is pasted into a synthetic image, and soap adds no dents
or raised geometry.

New ordinary domain plans choose 40% dried islands, 25% faint film, 25%
coalesced residue, and 10% retained ring/speckled styles within the soap class.
These are sampling weights, not exact per-run quotas. Primary class balances,
camera coverage, and unrelated dent/oil generation are unchanged. Explicit
legacy soap recipes retain their earlier parameters. All deposit materials
share one coat shader to avoid exceeding Cycles' closure limit on mixed spots;
instance masks and labels remain separate.

The bounded reference comparison uses 1936 × 1216 output, the supplied three
camera views, and mild independent lighting variation. It includes tiny/faint
spots and larger merged marks. The dark-camera framing is shifted to match
the supplied Aug13 session only in this comparison recipe.

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' -b --factory-startup -t 6 --python verification/render_soap_reference.py -- --output verification/soap_reference_20260923/final --check-visibility
.\.venv\Scripts\python.exe verification/report_soap_reference.py
```

The comparison script uses CPU rendering to reserve the desktop GPU for
training. Its `controls/` images render the same scene without soap to measure
the residue's RGB contribution; they are not dataset negatives. The report
keeps real reference crops outside `final/all/`. Preview seeds and these
development outputs should not be treated as held-out evaluation data.
Existing fleet jobs use immutable releases and continue with their current
recipes; their dent/fold restriction is not changed by this update.
# Inverted camera visibility controls (September 23)

The current `body-gap` recipe still targets only the 640 x 640 inverted camera:
50% Fold / 50% Dent primary images, 40% mixed, and 45/40/15 small/medium/large
instances. It now includes round, oval and paired dimples plus transverse,
wrinkled and soft buckles. Existing clean/handled/dirty, lighting, camera blur
and noise distributions remain independent of class. `background_variation`
adds small, absolute fixture offsets, jaw spacing, wheel height, reflectance,
roughness, texture scale and tint changes. Reapplying a row does not accumulate
changes. The inverted brass response also reduces the long continuous alloy
streaks observed in the first development renders.

`domain_render.render_sample` now checks **each geometric instance** against a
render with only that instance removed. Both share the same sampling grid,
materials, camera, render/noise seed and the final glare-corrected light powers
and exposure. Other defects remain. This avoids counting geometry masks alone
as visible evidence and works for mixed defects. The native image is reduced
to the model's 640-pixel long-edge scale before assessment.

Per-row `visibility_controls` can override the defaults in
`defect_visibility.DEFAULTS`: 8 support pixels, 4/255 p90 luminance change,
15% changed support, 6 connected changed pixels, and a shape/texture contrast
ratio of 1.5. The local render-noise floor raises the pixel threshold. Signed
spatial smoothing and the clean surface's texture contrast prevent mere grain
movement from passing as a visible dent. A broad shallow preview that passed
the first pixel-change test motivated this additional texture criterion.
These are engineering review thresholds, not calibrated human acceptance
limits or measured YOLOX accuracy. They should be revisited with real evals.

On failure, only that instance's depth is increased, with a maximum of two
repairs and the existing 0.25 geometry limit. Each repair rerenders geometry,
RGB, masks, glare and visibility checks. The original settings, failure metrics
and final instance specifications are retained in metadata. A candidate still
failing after three attempts raises an error before publishing any labels;
the worker never turns it into an unlabeled negative. Failed previews are kept
under `rejected`, outside the accepted image folder. Production retains the
existing commit/hash/resume protocol and cannot silently swap renderer versions.

`keep_visibility_controls: true` saves matched comparison PNGs under
`all/controls`; otherwise production removes these extra images after checking
and stores just the metrics. The guard costs one extra beauty render per
geometric instance, plus any bounded repairs. It is a quality tradeoff.
Material-only stains retain their existing mask/glare checks; this new geometry
gate does not claim to validate their RGB visibility.

Development review command (CPU only, six threads; desktop GPU stays available):

```powershell
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' -b --factory-startup -t 6 --python-exit-code 1 --python verification/render_visibility_robustness.py -- --output verification/visibility_review_new
.\.venv\Scripts\python.exe verification/report_visibility_robustness.py verification/visibility_review_new
```

The review includes clean controls with empty label files. Keep them as
negative examples if used later; the photographs are comparison references
only. Severe torn/open outlet geometry in the second supplied image remains
outside this closed-surface radial-deformation model. Existing immutable fleet
jobs are unchanged; a new fleet release is required to use these controls.

# Neck crescent and rolled mouth (September 23)

`neck_defect_plan.py` targets the two supplied `20260905_012931_613`
cam1130/cam2829 examples. Their source annotations use **Dent, class 1**.
The new opt-in styles are `CRESCENT_CREASE` (a short curved depression with
an unequal raised edge) and `ROLLED_LIP` (a connected neck buckle and crescent,
with a locally lowered mouth). Both are available in the Studio style selector.
General random style weights and class proportions are unchanged.

The rolled lip displaces both skins axially as well as radially. Its maximum
drop is bounded by the affected neck span so axial rings cannot reverse order.
The support mask includes the lowered rim. Counterfactual renders remove both
components on the original grid. At most one rolled rim instance is allowed
per pipe; other defect families can still be combined with it. This represents
a continuous folded wall, not a cut or missing metal.

The targeted recipe balances UPRIGHT / FOREGROUND and three variants: small
crescent, wider crescent, and rolled mouth. It uses native 640 x 640 capture,
seeded finish/light/blur/noise variation, background finish variation, and the
shared glare and visibility gates. A second visual iteration flattened the
overly tall first crescent, weakened its raised edge, and offset the mouth
collapse. The short, mottled alloy finish previously used for INVERTED now
also applies to UPRIGHT / FOREGROUND, reducing full-height vertical stripes.

```powershell
# Save an opt-in supplement plan; this does not launch or replace a fleet job.
.\.venv\Scripts\python.exe neck_defect_plan.py --count 3000 --output new_neck_plan.json
# Small CPU development review with the standard QA controls:
& 'C:\Program Files\Blender Foundation\Blender 5.1\blender.exe' -b --factory-startup -t 6 --python-exit-code 1 --python verification/render_neck_defects.py -- --output verification/neck_review_new --samples 64
.\.venv\Scripts\python.exe verification/report_neck_defects.py verification/neck_review_new
```

Counts must be multiples of six. This is a targeted supplement, not a proposal
to replace a balanced training set with only neck dents. Real photographs
appear only in the review page; rendered masks provide the synthetic boxes.
Visibility checks do not measure detection accuracy. The development examples
must not be treated as an independent real-world validation set.

## Targeted evaluation supplement (September 24)

The opt-in `eval-gap` profile addresses the September 23 23:21:43
evaluation. It renders only UPRIGHT, FOREGROUND and INVERTED, at the real
square-camera resolution of 640 x 640. It is separate from the older eight-view
production profile and the assembled conveyor scene. Both the fleet CLI and
`generate_domain_dataset.py` support it; see [running on another machine](GENERATE_TARGETED.md).

A 3,000-image plan has exactly 1,000 frames per view: 1,350 Fold-primary,
1,350 Dent-primary, and 300 clean controls. There are 600 two-defect and 600
three-defect frames, yielding 2,250 instances of each defect class overall.
All production specimens are assigned to train; real validation stays separate.
The clean controls intentionally have empty labels and should not be removed.

The recipe combines small round dimples, broad shallow presses, thin axial
neck folds, body buckles and the new neck crescents. It retains independent
finish, lighting, camera softness, sensor noise and background finish variation.
Compact mixed defects may be closer than the general 0.12 axial separation
only under the explicit `compact-separated-v1` policy, with a 0.065 minimum
and a footprint-dependent separation check. Larger overlapping supports still
fail planning validation.

Every instance uses the shared glare and counterfactual visibility gates at
model input size. At most two depth repairs are permitted per candidate.
This profile can then retry three deterministic visible-side angles, retaining
identity, footprint, class and nuisance settings. Exhausted candidates fail
closed; they are not converted into good images or published without labels.
Repair histories are stored and replayed by the dataset validator, which still
rejects unexplained geometry changes. These limits are visibility proxies,
not evidence of improved YOLOX accuracy.

`remote/fleet.py ready --nodes spark,agx --profile eval-gap --count 3000
--no-defects-only --allowed-defects FOLD DENT` renders 18 development samples,
checks output pairs and stages a production plan. Inspect these before starting
production. Fleet readiness automatically separates preflight and production
seed ranges; never merge the preflight test folder into real validation.

The completed review is `verification/crescent_neck_20260923/index.html`:
six size/camera variants plus one side-angle crescent, all accepted by both
guards. The side-angle render reproduced the off-center shoulder mark more
closely and passed without dimming the initial lighting. The v3 recipe places
small crescents 32–46 degrees around the visible side and widens the middle
variant's angular spread. The two review batches retain separate plans and
renderer fingerprints; none were merged into an existing training dataset.
