# Brass surface V4

The material study compares the supplied upright photograph, the GodsLight horizontal reference, and the selected full-frame source examples in `verification/dataset-study-v3`. Those images show uneven olive/brown finish, interrupted axial machining, sharper reflections on brighter streaks, and duller mottled regions. The first V4 material comparisons keep camera, lighting, shape, and image settings fixed against the preserved V3 shader.

The changes are:

- Corrected the Blender 5.1 socket name for directional reflection. The old material tested for `Anisotropic IOR Level`; the installed shader exposes `Anisotropic`, so the old guarded assignment had silently left it at zero. Both exposed-brass responses now use the connected axial tangent and a nonzero amount.
- A brighter brass conductor reference supplies the starting reflection color. A rougher exposed-metal response and a sharper burnished response are mixed along interrupted, seed-controlled drawing tracks.
- Dull dielectric patches and fine flecks represent the observed mottling. Their coverage and roughness vary spatially; they do not make the whole pipe uniformly rough.
- Slow, shallow normal variations break up overly perfect reflected bands. Existing fine grain and drawing scratches remain layered above those variations.
- Geometric orientation identifies the annular cut faces and the inside wall, giving the cut rim a brighter finish and the bore a duller response.
- The `Brass surface` panel offers Reference, Drawn, Mottled and Satin recipes, plus separate oxide and burnished-streak controls. These recipes preserve the camera, lights, pipe shape, and geometric defect.
- The GodsLight reference lighting aims a narrower source toward the shoulder, with reduced fill and a green/cool rig tint, to reproduce the darker olive body and concentrated shoulder reflection seen in the photograph. The tint belongs to the lights and resets when switching environments. The final V3/V4 review therefore includes this lighting adjustment as well as the revised material; camera and geometry are unchanged.

The generic starting color follows the brass example in the [Filament materials guide](https://github.com/google/filament/blob/main/docs/Materials.md.html#base-color): sRGB (0.98, 0.90, 0.59), converted to approximately (0.955, 0.787, 0.307) in scene-linear RGB. Filament distinguishes conductor reflection color from dielectric diffuse color. The olive control, oxide appearance and recipe settings are subsequent visual fits, not measurements of this particular alloy or its oxide chemistry.

Final reference-sized renders and the editable `Brass Surface V4.blend` are in `examples/brass-v4`. The original V3 dataset remains in `examples/challenge-v3`. New generated datasets use the new shader and record version 4. Old incomplete runs deliberately refuse resume after renderer source changes, so start a fresh output folder to use the new material.

Verification checks the actual anisotropy inputs, finite/idempotent material updates, all finish operators, unchanged shape/camera/lights, exact mask-pixel equality under material and lighting changes, and empty labels on a fully marked clean pipe. The control and mask checks are in `verification/brass-v4/checks/result.json`.

These are visual approximations. The photographs do not provide a calibrated light spectrum, surface reflectance measurement, or alloy composition. Reflected bands also depend on the inspection rig; no static color texture can reproduce those bands correctly for every lighting option.
