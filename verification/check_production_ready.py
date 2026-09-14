"""Read-only check of the saved Blender collection defaults and launcher."""
from pathlib import Path
import json
import runpy
import sys
import bpy

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root))
runpy.run_path(str(root / 'open_rolling_capture.py'))
scene = bpy.context.scene
config = scene.rolling_capture
assert (scene.render.resolution_x, scene.render.resolution_y) == (2400, 1200)
assert scene.cycles.samples == 192 and scene.cycles.adaptive_min_samples == 64
assert not scene.render.use_motion_blur
assert config.production_quality and config.randomize_defects
assert config.collection_target == 3000 and config.collection_pass_limit == 1000
assert (config.start, config.end, config.step) == (1, 144, 12)
assert config.camera == 'ALL' and config.trigger == 'DEFECT'
assert config.body_dents == 4 and config.twist_limit == 12
assert abs(config.groove_definition - 1.4) < 1e-5
viewports = [a.spaces.active.shading for screen in bpy.data.screens
             for a in screen.areas if a.type == 'VIEW_3D']
assert viewports and all(s.type == 'RENDERED' and s.use_scene_lights and s.use_scene_world
                         for s in viewports)
grooves = {slot.material for obj in scene.objects for slot in obj.material_slots
           if slot.material and slot.material.use_nodes
           and slot.material.node_tree.nodes.get('Fine groove shoulder normals')}
assert grooves
assert all(abs(mat.node_tree.nodes['Fine groove shoulder normals'].inputs['Distance'].default_value
               - .00098) < 1e-7 for mat in grooves)
result = dict(passed=True, resolution=[2400, 1200], samples=192, minimum_samples=64,
              sharp_exposure=True, scene_lighting=True, groove_materials=len(grooves),
              target_images=config.collection_target, camera=config.camera,
              trigger=config.trigger, random_seed=config.random_seed,
              body_dents_per_six=config.body_dents, maximum_twist=config.twist_limit)
(root / 'verification/production-ready.json').write_text(json.dumps(result, indent=2))
print('PRODUCTION_READY', json.dumps(result), flush=True)
