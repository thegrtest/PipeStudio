# Realism references and their use in Pipe Studio

Reviewed September 15, 2026. These are learning resources, not a claim that the generator is optically calibrated or that YOLOX transfer has improved.

| Resource | What it contributes | Application here |
|---|---|---|
| [TopChannel1on1 — supplied Blender 2.8 video](https://www.youtube.com/watch?v=9JEyA0FqIl0) | Visual modeling/material/scene workflow with a photographic brass reference. The available transcript contains music rather than spoken instructions. Selected frames, description and transcript were inspected; the entire video was not watched. | Treat the reference as a surface and lighting target. Its stylized scene and animation are not the inspection-camera target. |
| [Blender Guru — Photorealism Explained](https://www.blenderguru.com/posts/photorealism-explained) | Workflow connecting shape, materials, lighting and photographic appearance, with further resources on surface imperfections. | Compare all four against real frames, and isolate individual light sources before adjusting them. |
| [Poly Haven — Photoscanned Texture Creation Process](https://blog.polyhaven.com/photoscanned-texture-creation-process/) | End-to-end acquisition and processing of real surface textures, including material setup. | A controlled material capture is a useful next input. Inspection JPEGs contain reflections and camera processing; copying those colors onto a mesh would bake the current illumination into the material. |
| [Poly Haven — texture capture requirements](https://blog.polyhaven.com/texture-contracts/) | Lighting-free albedo, recorded surface dimensions, and separate roughness/normal/displacement maps. | Preserve physical texture scale and separate reflectance, roughness and surface normal variation. Current shader remains procedural; no real defect pixels are copied. |
| [Blender — Cycles light settings](https://docs.blender.org/manual/en/5.0/render/cycles/light_settings.html) | Area-source beam spread and lighting controls. | Replace the small frontal key with a larger off-axis diffuser; retain independent camera/light variation and glare checks. |
| [Blender — denoise node](https://docs.blender.org/UATEST/manual/en/dev/compositing/types/filter/denoise.html) | Detail preservation depends on feature passes and sampling. | Review full-resolution renders, not only thumbnails; compare production sample settings with higher-sample controls before trading detail for speed. |
| [Blender — linear color workflow](https://docs.blender.org/manual/en/5.0/render/color_management/color_spaces.html) | Scene-linear rendering and correct interpretation of data maps. | Keep material data separate from display conversion. A cinematic tone transform is not automatically a match for the machine's processed JPEGs. |

## Applied in this revision

- Replace dense, continuous fine gold bands with weaker interrupted drawing marks, broader uneven tracks and resolved fine grain.
- Measure directional surface-detail power from 21 overlapping patches in three clear body ROIs. Check those ROIs against the real labels. Retain only smoothed aggregate spectra and generate new random phases for each specimen; no reference pixel pattern is placed on the pipe. The spectrum still reflects the source cameras and is an appearance estimate, not a measured material map.
- Vary roughness and micro-normal response alongside reflectance. Add sparse tiny handling traces independently of the defect class; clean pieces remain cleaner.
- Give fixture recesses rounded, slightly irregular edges and less uniform reflected light.
- Diagnose the persistent shoulder rectangle with lamp ablations, then enlarge and reposition its source. Keep native camera dimensions and existing labels/masks.

## Next measurements that would reduce guesswork

Capture a fixed pipe, a neutral reference and a reflective reference at the pipe position under several exposure settings; record camera gain/exposure, lens and light placement. For metal, a single inspection photograph cannot uniquely separate reflectance, surface roughness and illumination. Multiple lighting directions and views are more useful than adding arbitrary texture. Controlled material capture would be new input; it has not been performed here.

Use fixed real development images for adjustment and a separate real test set for the eventual model comparison. Visual similarity and crop statistics can identify mismatches, but cannot establish detection accuracy or prove transfer.

## Local detail follow-up

`brass_microdetail.py` adds unique physical-scale contact patches, interrupted short traces, sparse tiny specks and uneven rim burnishing. Its packed data texture drives reflectance, roughness and shallow normals together. Contact areas also reduce the fine grain, leaving quiet and busier regions instead of equal-density texture everywhere. It uses the specimen seed and finish controls; camera, lighting and defect class cannot choose a different pattern. Clean finishes have fewer marks. Existing large stain and geometric defect generators retain their labels.

The native-size review is [here](verification/microdetail_20260915/index.html). All 21 previews across eight environments validated; paired lighting preserved the same detail pattern, labels and geometry. Repeated Blender updates reused the same image/node allocation. The detail-map calculation took about 0.11 seconds for a 1536 × 1024 map on this workstation; this is only material preparation time, not end-to-end rendering throughput.
