# Verified prototype

Tested locally with Blender 5.1.2 / Cycles and the RTX 5080 GPU.

- Reference: 1536 × 1024, 96 samples, 4 visible defect instances spanning all three classes.
- Seeded batch: 8 images at 960 × 640, 32 samples, seeds 1000–1007, ±65-degree axial rotations. 34 visible defect instances.
- Integration cases: 1 fully clean frame and 1 frame with all 4 defects rotated to the underside. Both produced empty detection labels; underside masks were empty.
- All 11 images passed binary-mask, pixel-count, mask-derived bounding-box and YOLO-coordinate validation. Output hashes passed where recorded by the batch generator.
- Completed 8-image batch resumed successfully without re-rendering; generator/version/settings and output hashes were checked.
- Deterministic recipe comparison passed. Both successive Blender sidebar rebuilds passed. All tested plastic-shell edges were manifold.
- Inspected the final reference image and a randomized frame with label overlays. Materials remain an initial procedural approximation of the photo and approved concept.

Review galleries and machine-readable validation results are under each output folder's `review/`. Integration assertions are in `verify_blender.py`, with results in `output/integration_checks/checks.json`.

Blender could not write optional user thumbnail/extension caches under the sandbox. Scene, image, mask and metadata saves succeeded. The scene builder directs the OptiX cache into this lab's output directory.

No trained detector was run. No claim of calibration, impact simulation or real-data accuracy is made.
