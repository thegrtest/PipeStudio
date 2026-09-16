# September 14 evaluation-driven generation revision

The visual review covered 18 real scenes across three checkpoints. It found
Fold/Soap/Dent confusion, high-confidence detections on fixtures, missed broad
shallow dents, incomplete boxes, and missed additional defects. The run did not
load ground truth, so these observations are not measured accuracy or evidence
that any checkpoint is the overall winner.

The new `yolox` recipe is `real-eval-20260914-v2`, appearance version 10.

- New `SHALLOW_SWEEP` dents have a broad, rounded, shallow depression without a
  circular crater rim. Their support masks cover the center and sloping flanks.
- New `SOFT_BUCKLE` folds have an unequal rounded lip and soft depression. They
  favor the neck/shoulder, often at the silhouette. Narrow axial pinches and all
  six legacy shape families remain available.
- A 3,200-image plan retains 320 good, 720 primary images per defect class, and
  400 images per setup. There are 1,152 mixed images; 288 contain an additional
  primary-class instance. Total instance counts are 1,080 per class.
- Finish, light regimes and reflective fixture conditions are stratified by
  primary class within each camera. Thirty percent of every class, including
  good, sees stronger fixture illumination/lower hardware roughness. Reflections
  are rendered by the existing physical hardware and lamps, not pasted marks.
- Each geometric instance keeps its own visible mask and label. Empty labels
  only represent generated sound specimens. Glare gating remains enabled.
- Native output dimensions, aspect ratios and current camera matching remain.

`verification/eval_refinement/index.html` contains 21 validated previews. The
same-specimen lighting pair has identical geometry, binary masks and labels,
but different beauty images. These paired controls are **review only** and
must not enter random train/validation splits. They are not additional training
samples in the independent production recipe.

The prepared cycle is `../BrassEvalRefined_Ready_20260914`. Use its `Start Cycle.cmd`
to run its saved renderer. No fleet release is installed and no current cycle
is stopped by this change. Existing saved plans do not retroactively gain the
new recipe. The fleet's existing defects-only default remains explicit; use
`--no-defects-only` on a new fleet plan to retain the good/hard-negative examples.

The reviewed training configuration already disables Mosaic/MixUp. Keep that
baseline fixed while testing this data change, and judge the result with real
labels. The real source currently covers Fold/Dent rather than complete stain
ground truth, so Soap/Oil accuracy still needs a separately verified real set.
