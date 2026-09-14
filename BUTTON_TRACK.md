# Brass button track — exterior inspection

Open **Open Inspection Workspace.cmd**. The latest saved workspace starts in **Flashlight → Brass button track**, with the pipe mode and earlier flashlight environments still available. Select **Brass button track · 3 cameras** in the Inspection Studio sidebar to rebuild this environment in another integrated scene.

The current workspace opens in **Reference comparison**, an estimated 55° view fitted from the supplied photograph. **Shell length scale** is now editable and defaults to 1.0 (previously fixed at 1.25). The regular Front 45°, Rear 45° and overhead cameras remain the three views exported by **All three cameras**. Select **Current camera** to export the reference angle with the same labels and crops. Both the reference angle and shell length remain estimates, not measurements.

`examples/reference-match-study/final` contains all three inspection views plus the reference comparison. This pass enlarges the recessed FEDERAL/12 stamping, rounds the stamp edges, adds a subtle trough finish, widens the button seat by 12%, and gives the button a brighter alloy finish. The outer brass lip remains flat. Polished foreground aprons supply the reflected brass cue. The capture preset uses key/rim 1500, fill 145, exposure −0.60 and noise 0.007, with slightly stronger optical softness and highlight scatter confined to beauty images. Appearance version 4 identifies these changes.

Recipe version 12 adds seeded asymmetric body dents: offset depressions, flattened patches and creased shapes with localized displaced shoulders. Version 11 rows migrate without changing defect targets or removing the four-dent collection rule. One-shell updates in rows carrying that rule keep exactly four body-dented shells. Printing, ordinary residue, stamps and reflected objects on the conveyor introduce no extra defect classes. New geometry/view exports receive fresh masks; old dataset images are retained.

The exterior has a burgundy ribbed plastic body, a brass collar with an assembled screw-joint seam at the plastic boundary, a closed brass face with fine concentric grooves and recessed reference-style FEDERAL/12 stamps. The center button has a continuous shallow crown, rounded shoulder, recessed joint and raised concentric brass seat. A separate pale alloy finish varies fine forming grain, polishing and very faint concentric lines by specimen; highlights come from the scene lights. Its crown remains behind the rolled perimeter. The entire button and seat still belong to Brass Face, and existing dent/scratch controls deform and label them. `examples/button-detail` contains a close-up, clean three-camera exports and a center-dent check.

The brass rim has a **flat front annulus**, with only a small bevel at its outer edge, a curved rear shoulder and a shallow groove behind it. The center button remains domed. The rim's outer radius is `.518`, about 7% wider than the straight brass collar. The face and collar use coincident boundary vertices and denser sampling around the edge, while retaining their separate Brass Face/top labels. These proportions are estimated from the reference, not measured dimensions. `examples/local-shell-updates/flat_lip.png` shows the current planar rim.

The plastic end uses six individual thick flaps with twisted seams, curved fold shoulders and visible undersides. **Product geometry → Crimp tightness** compacts the shoulders, sharpens crease sides and forms a clearer rolled margin; its default is `.85`, and `0` restores the broader profile. Closure twist and fold depth remain editable. The crimp face has a smoother finish to narrow its crease reflections. A clean face closes at the center and stays below the rim. This is a geometric approximation of a tube being twisted and pressed closed; it is not a thermoplastic or impact solver.

Body print version 3 uses the supplied photograph's actual **FEDERAL** ink shapes, arc logo and separate **2¾\" / 70mm** markings. Local paint brightness is removed to produce a scalar ink mask; the photograph's RGB shading is not pasted onto the model. Letter proportions, word spacing, logo shape and broken stamp edges come from the source, replacing the previous Arial two-line approximation. The brand and size markings occupy separate bands around the tube. Seeded registration exposes different bands on different shells. The outward-facing mapping keeps the F unmirrored, beginning toward the brass end, and the printing rotates with alternating shells. Reference ink wear is `.18` so the source's existing wear is not excessively faded again. All ink images are packed into the workspace and remain excluded from defect labels.

**Surface finish → Dust and debris** adds sparse matte grains and occasional tiny fibers on the plastic and brass. The default is a light `.22`; `0` disables it. Dust is seeded in the object's own coordinates, so it stays attached through rotations and is identical across the three camera views. It affects only the surface shader: no dirt defects, masks or boxes are added, and Clean can still look lightly dusty. Varied capture conditions also vary the amount gently; zero remains off. `examples/dust-study` includes a dust-off/on comparison verified to have identical region masks and empty defect labels.

The brass uses the tapered-pipe workspace's V4 material, adapted to this object's axis and closed face: exposed brass, patchy oxide, polishing, drawing grain, handling marks and small surface irregularities. Polymer has seeded pigment variation, fine axial texture, shallow ribs and handling scuffs. Opposing cool inspection bars at 45 degrees make blue-white reflection bands along the bodies; low front/rear lights reveal the brass faces. Light angle, span, softness and color cast remain adjustable. Plastic roughness and reflection strength are independent of brass; fine grain, dust and handling marks are shared finish controls. These are Cycles renders of editable geometry, not generated bitmap mockups. The lettering displaces the cap mesh inward and belongs to Brass Face, with no extra defect labels.

### Reference and clean appearance

**Surface finish → Reference finish / Clean finish / Previous satin finish** changes materials and camera response while retaining every shell, defect, camera pose and light setting. This is separate from **Surface defect → Clean**, which removes injected defects. The saved workspace uses Reference finish and Photo lighting, including four body-dented shells.

The current reference finish restores the earlier sharper reflections: body roughness `.24`, reflection strength `.45`, modest clear coat `.055`, and independent crimp roughness `.185`. Uneven finish is restrained at `.28`, rib polishing is `.72`, and pale groove residue is `.40`. The previous lower-reflection settings are retained in **Previous satin finish**. Printing, dust, residue and dull patches follow the specimen and remain normal, unlabeled appearance.

Adjust **Plastic roughness**, **Plastic reflection strength**, **Plastic clear coat**, **Uneven plastic finish**, **Groove highlight polish**, **Pale groove residue**, **Crimp roughness**, and **Body ink wear** individually. **Lighting → Optical softness**, **Highlight scatter**, and **Camera noise** control the approximate inspection-camera response. Softness is specified at a 1200-pixel image width and scales with export resolution. Zero disables these camera effects; label passes bypass them at every setting.

Clean finish restores more even surfaces and clearer printing, reduces brass oxidation, and disables dust, residue, finish marks, optical softness, scatter and noise. Its off settings remain off in varied dataset captures. Switching presets is undoable. For a custom look, adjust after applying a preset and save the `.blend`; all values travel with exported metadata and background jobs (appearance version 8).

`examples/polymer-finish-study` contains the previous workspace, both editable finish variants and controlled comparisons. The appearance presets were checked with identical geometry, region masks and defect masks. The reference is an image-based visual estimate, not a measured camera/material calibration.

**Lighting → Photo lighting / Earlier lighting** selects the new continuous transverse strip or the earlier segmented bars without changing the specimens. The photo rig produces more even upper-body reflections across the row, with a restrained side light and a dark reflective apron. Its front and rear lamps remain physically fixed across the three camera views. Key/rim power, light width/span, angle and **Fixture distance scale** remain editable. The continuous strip spans the row as the count changes; distance changes scale source size and nominal power together. **Surface finish → Track reflection surface** restores the earlier metal apron if wanted.

`examples/reference-recovery/Photo recovery.blend` and `examples/button-track/Brass Button Track.blend` contain the current four-dent workspace. The separate `Undamaged photo comparison.blend` uses the same reference finish and framing with defects removed only for comparison to the source photograph. It does not replace the four-dent collection row. The final exports include all three standard views, the reference comparison view, labels, and automatic crops.

The latest finish pass distributes printing around the full circumference, varies transfer pressure and longitudinal registration, and gives individual shells subtle pigment, polish and oxide differences. Fine axial roughness breaks up the polymer reflections. The conveyor and guides have restrained directional contact wear. The reference preset uses narrower inspection lights (`key_span=.45`, `light_softness=.25`) to reveal shallow dents. `examples/realism-refinement` contains controlled before/after exports; normal finish changes were checked against 90 unchanged region and defect masks. These changes affect subsequent renders; existing dataset images are retained.

## Cameras

The image-only groove/light study is saved under `examples/groove-light-study`. The BODY shader uses the actual mesh rib count and phase to add fine shoulder normals, interrupted crest polishing and sparse pale channel residue. It reads the same undeformed coordinates as the printing, so the details follow dents and twists across views. No extra body polygons or defect IDs are added. Texture strength controls the fine relief; Finish marks controls the residue, with zero disabling residue. The normal dust control remains separate.

The reference rig now combines a soft central emitter and two narrow bars on each side of the row, with lower green-tinted face lighting. Its closer placement makes the body highlights fade along the tube. Key/rim power, angle, span and softness still control the fixture; the current preset uses key/rim power 1150. `appearance_version: 3` identifies this pass, and metadata records the actual fixture transforms, sizes, colors and powers. The physical shell geometry, flat brass lip and defect recipes remain unchanged. This is an approximation from one photograph; the reference does not uniquely identify the real lights or surface residues.

**Oblique projection → Inspection perspective** gives the two 45° views natural near/far magnification. **Orthographic** retains constant magnification; overhead remains orthographic in either mode. Changing projection preserves the defect recipe. Export metadata includes the projection matrix, lens, sensor width, shifts and world transform; `appearance_version: 2` identifies the refined finish. Region masks were independently checked against camera rays in both modes.

**Camera → Preview camera** selects Front 45°, Rear 45° or Straight down. The oblique cameras are on opposite ends of the row, both at 45° elevation. The overhead camera points vertically down. Each is a separate Blender camera object. The row remains the same physical specimen when cameras change.

**Export cameras → All three cameras** produces three images per specimen row. A batch count of 100 means 300 images. **Current camera** produces one image per row. Zoom, framing and aspect ratio apply to all cameras. The rear view reverses screen order; flashlight IDs remain tied to the physical row, not pixel order.

## Region classes

The user-confirmed mapping is:

| ID | Class | Exterior surface |
| --- | --- | --- |
| 0 | top | Curved side of the brass collar |
| 1 | body | Long plastic housing |
| 2 | Brass Face | Brass end face, including the center button |
| 3 | Plastic Face | Entire molded plastic end face |

Each region of each flashlight has its own visible instance mask. Hidden regions retain metadata and an empty mask, and receive no detection box. These are region labels, not defect labels.

## Defects

Choose **Selected flashlight**, a row index and a **Defect region** to place a dent or scratch on any of the four exterior regions. Plastic scratches are supported in this environment. For curved sides, position is along the housing. For end faces, position moves the defect outward from the face center; angle rotates it around the face. Width controls the footprint and depth controls actual deformation. The center button belongs to Brass Face.

**Mixed row** starts with about 80% of shells defective (five of six by default), with a guaranteed majority for every supported row size. Defect targets span the four exterior regions, with independently varied positions, depths and shapes. Dent families include rounded, elongated, overlapping, oblique, wrinkled and branched forms; scratches vary in count, length, width and direction. Dents and scratches deform the actual surface. Scraped surface finish also changes within scratch support. Clean removes injected defects while preserving normal finish variation and region labels. Clean probability in batch generation applies to an entire row. The seed, geometry and region IDs are shared by all three camera images. Keep those related views together when making train/test splits.

**Update one shell** (formerly New defect) changes exactly one shell per click. Mixed row advances through the row in order and wraps around; Selected flashlight updates its selected index. A clean shell receives a defect, while an already defective shell gets a new defect shape or placement. Only the old/new affected regions are rebuilt: other shells, finishes, cameras, track and lighting retain their objects. The base seed stays fixed, and a saved row revision makes the sequence reproducible. Changing the seed or row/defect controls deliberately starts a new recipe; camera, lighting and finish changes retain local defect edits. Current-image export sends the edited recipe to the background worker, while randomized batches continue to create independent rows. `examples/local-shell-updates` contains before/after exports and timing/reuse checks.

Defect IDs are **0 plastic_dent**, **1 metal_dent**, **2 metal_scratch**, **3 plastic_scratch**, **4 open_center**, **5 protruding_crimp**, and **6 body_twist**. Existing IDs are retained. Masks describe visible procedural support, not a physical acceptance threshold.

**Shallow dent** selects a low-depth, broad, smooth indentation. Mixed rows and one-shell updates now sample more small depressions instead of forcing a large minimum depth. The depth control still allows deeper dents. Printing, fine ribs, material grain and dust use undeformed material coordinates, so they stretch with the plastic rather than staying painted in space.

**Body twist** targets the plastic body. Signed twist degrees control direction and severity, from subtle single-digit rotations to large twists up to 140°. **Twisted body fraction** controls how much of the length takes up the twist; **Twist center along body** positions it. A smooth transition leaves the collar attached and rotates the plastic closure to match the far end. Larger twists add bounded ovalization and helical buckles. Zero twist produces no twist defect. The twist mask covers the sheared band of the BODY region; the rotated but otherwise undamaged plastic closure remains only a Plastic Face region label. This is controlled exterior deformation, not a calibrated polymer failure simulation.

One-shell twist updates reuse the intact end mesh and only rotate it. Material slots and smoothing are assigned in bulk. In the local benchmark, repeated twist updates took a median of about 0.32 seconds, excluding viewport or image rendering. The material assignments were independently checked against the previous path. Current-image worker exports preserve the modified recipe, including after float-valued settings are read back from Blender.

`examples/defect-realism-study` contains clean, shallow/moderate dent and 8°/35°/100° twist comparisons. `exports/shell_defects_pilot_v1` is the prepared 24-row pilot (72 images) with defect and region YOLO datasets, masks, COCO splits, crops and review galleries. Its 48 training and 24 validation images keep each row's three views together, with all seven classes and clean examples represented in both splits. Read its README and validation report before scaling up.

Choose **Open center** to withdraw the folded tips and create an actual aperture. **Opening / face radius** controls its size. The flaps have thickness and inner edges; there is no painted black disk over a closed mesh. The aperture mask includes the visible gap and withdrawn tips. An annotation-only surface fills the aperture during the defect ID pass; it is hidden in beauty and region passes. Region masks continue to follow whatever physical surface is visible through the opening.

Choose **Protruding crimp** to push the folded center past the nominal rim. **Center height above rim** sets its height, **Raised area radius** controls its spread, and irregularity/angle vary asymmetry. This represents an outward-displaced closure without inferring a battery or another internal cause. Both crimp buttons target Plastic Face. Use Selected flashlight to isolate one unit, or Mixed row to apply the selected crimp condition across the row. With Dent/Scratch selected, Mixed row also samples crimp failures on plastic-face targets. Clean removes all injected failures.

The new classes work with all three cameras, automatic crops, region/defect masks and background batch export. Batch randomization varies opening size, protrusion height and spread. `examples/crimp-study` contains closed, open and protruding examples with all three views and tight detail renders.

## Export files

In **Inspection Studio → Batch**, choose resolution, samples, output directory and specimen rows, leave **All three cameras**, **Varied inspection conditions** and **Automatic crops** enabled, then click **Auto-generate inspection images**. This uses the same background export worker as tapered pipes. It automatically varies defect severity and shape, finish, illumination, exposure, small pose/framing offsets and sensor noise. Reference conditions keeps the lighting, pose and finish control values fixed while specimen identity changes. A fixed seed reproduces the capture recipes. Capture noise differs by camera.

- `images/`, `labels/`, `masks/`: rendered images, defect YOLO labels and binary defect masks.
- `regions/images/`, `regions/labels/`, `regions/dataset.yaml`: a separate standard YOLO dataset for the four regions. Images use hard links where supported, with copies as a fallback.
- `region_masks/`: binary masks for individual visible region instances.
- `annotations.coco.json`: defect boxes from workspace batch export.
- `regions.coco.json`: region boxes, flashlight IDs and camera/specimen identities.
- `metadata/`: both annotation streams, exterior geometry recipe, camera matrix and view identity.
- `label_passes/`: diagnostic color passes used to decode visible masks. They are not training images.
- `crops/flashlight/`: automatically extracted full-flashlight crops for each visible unit.
- `crops/TOP/`, `crops/BODY/`, `crops/BRASS_FACE/`, `crops/PLASTIC_FACE/`: visible region crops. Tiny or largely occluded slivers are omitted from crops; their region masks remain available.
- `crops.json`: crop paths, source-image boxes, camera and specimen identities, flashlight IDs, and defect boxes translated into crop coordinates. Crops preserve the rendered source pixels without resizing.

The current scene or a batch exports through the existing Blender background worker. The stop button completes the current specimen's camera set before stopping.

The darker reference preset reduces exposure and ambient fill while retaining bright inspection reflections and readable end faces. `clean_front_45.png` is produced through the same capture exporter as dataset frames, including its sensor noise; its clean labels, region masks and crops are in `clean-reference/`.

Validate both annotation streams and create review galleries:

```powershell
& '.\.venv\Scripts\python.exe' flashlight_lab\dataset_review.py 'EXPORT_FOLDER'
& '.\.venv\Scripts\python.exe' flashlight_lab\dataset_review.py 'EXPORT_FOLDER' --regions
```

Reference views and region/defect galleries are under `examples/button-track`. Integration checks in `verification/verify_button_track.py` compare region masks against independent Blender ray casts, verify opposite 45° cameras, and generate two clean specimen rows from all cameras to check that clean defect labels remain empty while region labels are populated.

This is an exterior appearance model, not a calibrated simulation of the actual camera, alloy or impact mechanics. Exact dimensions, stamp tooling and measured camera/light response remain uncalibrated. Use real held-out inspection images to judge model performance; the exported metadata explicitly records `calibrated: false`.
