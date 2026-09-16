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
