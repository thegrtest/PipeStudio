# Next YOLOX transfer experiment

The first model is the baseline. Keep its training data and settings fixed while
it finishes; new rendering should go to a separate folder. This candidate recipe
addresses observed gaps. It is not yet a measured improvement in real accuracy.

## Evidence from the current data

The September 14 read-only audit found 10,544 synthetic images with valid labels,
1,076 explicit empty labels, and only 16 mixed-class images. It also found six
orphan label files whose images are absent; no files were removed or repaired.
Fold/Dent instances number 4,119/4,091 versus only 638/636 Soap/Oil instances.
Naively sampling the combined archive therefore does not balance the classes.

At a 640-pixel letterbox input, median fold thickness is 30.40 pixels in the
archive, 14.21 in August 19 real images, and 11.57 in August 20. The recently
refined generator's 80-image review was much closer (15.37). Preserve that
new small-fold distribution; do not let the older large defects dominate the
next experiment simply because their archive is larger. Dents have a different
size distribution and should not be shrunk indiscriminately.

The August 19 real set has mixed Fold/Dent labels in 162/867 images. Those
annotations support retaining multiple defects and reviewing Fold/Dent confusion.
The two August real sources contain no Soap/Oil class labels. They cannot verify
four-class precision without a separate stain annotation review.

Read the local audit at `verification/yolox_readiness/index.html`; the JSON
contains dimensions, missing-label checks, and size counts by camera/class.

## Candidate generation mix

The `yolox` profile prepares 3,200 independent specimens:

| Item | Mix |
| --- | --- |
| Environments | 400 images in each of all eight setups |
| Good specimens | 320 (10%), including clean, handled and dirty finishes |
| Primary defect classes | 720 each Fold, Dent, Soap, Oil |
| Mixed defects | 1,152 images: 40% of defective images; two distinct classes |
| Repeated defects | 288 of those mixed images add another primary-class instance, including two dents plus a stain |
| Total defect instances | 1,080 per class; 4,320 in total |
| Geometric size bins | 45% small, 40% medium, 15% large |
| Fold shape families | 50% axial pinches, 20% soft shoulder buckles, 30% across six legacy families |
| Dent shape families | About 45% broad shallow sweeps, plus all six legacy families |
| Surface condition | 30% clean finish, 35% handled, 35% dirty; separate from defect class |
| Capture conditions | 70% matched, 20% moderately softer/noisier, 10% mild framing/light shifts |
| Fixture reflections | 30% stronger reflections and smoother hardware; same proportion for good parts and every defect class |

Capture categories are stratified within each primary class and environment.
The existing 70/20/10 mild/broader/stress light distribution remains. Additional
camera perturbations stay bounded: optical response 1.10–1.35 times baseline,
noise 1.15–1.60 times baseline, or up to 3% zoom and 0.18 EV exposure variation.
Native dimensions and aspect ratios remain unchanged. The glare gate rejects
washout; masks retain every visible instance. Export metadata reports each
defect's width/thickness at 640 and 960, flagging values below 4/8 pixels without
silently deleting small labels. Glare rejection alone does not prove visibility.

The 40% mixed allocation deliberately oversamples coexistence for training;
it is not an estimate of factory defect prevalence. Good images with realistic
texture, dirt and bright fixtures help measure false alarms. Finish dirt is
not a stain label unless the generator creates a localized annotated deposit.

## Run the candidate when capacity is available

`Generate YOLOX Robust Dataset.cmd` starts a new local cycle. The prepared cycle
is `../BrassYOLOXRobust_Ready_20260914`. Its resume shortcut uses the saved plan.
Root-source changes after preparation require a new plan folder.

The September 14 evening revision is `real-eval-20260914-v2` (appearance 10).
Existing prepared plans/releases retain the earlier recipe. The new prepared
cycle is `../BrassEvalRefined_Ready_20260914`; its renderer is saved with the
cycle so later source edits do not break its resume checks.

New local/fleet CLI plans default to `--profile yolox`; `--profile reference`
retains the previous 25% mixed recipe for comparison. Existing jobs keep their
immutable release and saved plans. The fleet's current defects-only preference
was preserved. To deliberately include good examples in a NEW fleet plan:

```powershell
python remote/fleet.py prepare --profile yolox --no-defects-only --count 3200
```

Use the existing fleet readiness/start flow after preparation, when resources
are free. No training, fleet deployment, or additional full generation cycle
was started during this refinement.

## Train and evaluate in a useful order

1. **Finish model A unchanged.** Record the checkpoint SHA256, training dataset
   inventory, input size, preprocessing, confidence and NMS settings. Score
   saved early/middle/final checkpoints against the same real development set;
   synthetic validation alone is not evidence of real transfer.
2. **Model B: change the generator data only.** Use the new generation set at
   the same input size and training settings as A. Retain explicit negatives.
   Compare per-camera Fold/Dent recall, thin-fold recall, false positives and
   Fold-to-Dent confusions. Review false positives on fixtures manually.
3. **Model C: test gentler augmentation.** Keep B's dataset fixed. The reviewed
   training configuration already has Mosaic and MixUp disabled; keep them off.
   The companion `yolox_experiment_options.json` proposes restrained
   spatial transforms and no multiscale downsampling. This is a trial recipe,
   not a change to the running model. Inspect augmented training batches at
   their actual input size before committing to a long run.
4. **Then test 960 input if thin-fold recall remains weak.** Changing 640 to
   960 increases each defect's linear pixel size by 1.5. Measure throughput,
   memory and real recall; raw 1936-pixel renders alone do not imply the model
   sees that detail. Keep inference preprocessing consistent with training.
5. **Mine targeted failures.** Next cycles should emphasize the camera, size,
   shape or material conditions that produce repeated errors. Keep a balanced
   control set so fixing one failure mode does not hide a regression elsewhere.

YOLOX exposes the augmentation/input controls used here in its
[official experiment configuration](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/yolox/exp/yolox_base.py).
Its [custom training guide](https://github.com/Megvii-BaseDetection/YOLOX/blob/main/docs/train_custom_data.md)
also discusses adjusting augmentation strength. The specific values here are
our proposed ablation for small metallic defects, not official recommended values.

August 19/20 and the inspected reference views already influenced renderer
development. Use them for development, not a claimed untouched holdout. Reserve
fresh acquisition sessions and entire physical-part sequences (all camera views)
for the final test. Keep derivatives of the same specimen in the same split.
Do not add real reference images to the synthetic training bundle.

## Score saved predictions without retraining

`score_yolox_predictions.py` consumes native-pixel detections after NMS and
reversing the model resize, clipped to image bounds. Export this schema from the inference application:

```json
{
  "metadata": {
    "checkpoint_sha256": "REPLACE_WITH_ACTUAL_64_HEX_SHA256",
    "input_size": [640, 640],
    "nms_threshold": 0.65,
    "export_confidence_floor": 0.01,
    "box_space": "native_xyxy"
  },
  "images": [
    {"file_name": "example.jpg", "detections": [
      {"class_id": 0, "score": 0.8, "bbox_xyxy": [620, 260, 720, 320]}
    ]}
  ]
}
```

Every evaluated image requires an entry, with `detections: []` when none are
found. Incomplete prediction coverage raises an error instead of silently
inventing empty predictions. Class IDs are 0 Fold, 1 Dent, 2 Soap, 3 Oil/acid.
The export confidence floor must not exceed the threshold being scored. Each
report records a ground-truth label/dimension hash so annotation changes can
be detected when comparing checkpoints.

```powershell
python score_yolox_predictions.py --real ../BrassModel11/all/2026-08-19GodsLight --predictions predictions.json --output evaluation/model_A_aug19.json --classes 0,1 --confidence 0.25 --iou 0.5
```

The result includes fixed-threshold precision/recall, per-camera counts,
recall by thickness, wrong-class overlaps and an image-level failure queue.
It is not COCO AP. Use only classes with complete ground truth; review stain
annotations before including classes 2/3. No fresh checkpoint evaluation has
been run as part of this change.
