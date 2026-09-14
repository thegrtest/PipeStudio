"""Dirt controls must not alter defect geometry or training split identity."""
from pathlib import Path
import json
import sys
import bpy
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root))
import pipe_studio as studio
import rolling_capture as capture
import rolling_quality as quality
import rolling_randomization as randomization
studio.register(); scene = bpy.context.scene
options = capture.random_options(scene.rolling_capture)
base = {**studio.settings_dict(scene.pipe_studio), **capture.quality_options(scene.rolling_capture)}
rigs = randomization.rigs_in(scene)
dirty = randomization.make_recipe(base, rigs, options, 0)
clean = randomization.make_recipe(base, rigs, {**options, 'mix_soiling': False}, 0)
assert dirty['defects'] == clean['defects']
assert dirty['split_group'] == clean['split_group']
assert dirty['recipe_sha256'] != clean['recipe_sha256']
assert all({k: v for k, v in item.items() if k != 'normal_appearance'} == other
           for item, other in zip(dirty['items'], clean['items']))
assert len(rigs) == 31 and not scene.get('video_only')
counts = {name: sum(i['normal_appearance']['category']==name for i in dirty['items'])
          for name in ('clean', 'light', 'heavy')}
assert counts['clean'] >= 10 and counts['heavy'] >= 15
report = dict(passed=True, unchanged_defect_geometry=True, same_split_group=True,
              appearance_counts=counts, collection_target=scene.rolling_capture.collection_target)
(root/'verification/rolling-soiling-recipe.json').write_text(json.dumps(report, indent=2))
print('SOILING_RECIPE_VALIDATED', json.dumps(report), flush=True)
