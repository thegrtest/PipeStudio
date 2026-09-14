"""Apply the user's dirt-off setting and replace the dirty collection."""
from pathlib import Path
import json
import sys
import bpy
root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root))
import pipe_studio as studio
import rolling_capture as capture
import rolling_quality as quality
import rolling_randomization as randomization
from rolling_supervisor import is_active

previous = root/'exports/rolling_shell_captures/20260913_105946_3291e2'
assert not is_active(previous), 'The previous collection is still finishing its current image'
assert json.loads((previous/'status.json').read_text())['state'] == 'cancelled'
studio.register(); scene = bpy.context.scene
config = scene.rolling_capture
config.mix_soiling = False
studio.SUSPENDED = True
try:
    scene.pipe_studio.dust_amount = 0
    scene.pipe_studio.groove_residue = 0
finally:
    studio.SUSPENDED = False
transform = scene.view_settings.view_transform
studio.configure_renderer(scene); scene.view_settings.view_transform = transform
p = quality.configure(scene, {**capture.quality_options(config),
    'resolution': config.resolution, 'samples': config.samples})
before = json.loads(scene['rolling_randomized_recipe'])
rigs, source, spec = randomization.randomize(scene, p, capture.random_options(config))
assert spec['defects'] == before['defects'], 'Dirt-off must preserve defect geometry'
assert all('normal_appearance' not in item for item in spec['items'])
materials = {slot.material for rig in rigs for obj in rig.children for slot in obj.material_slots if slot.material}
assert all(not mat.get('normal_soiling') and mat.get('inspection_dust_amount', 0) == 0 for mat in materials)
assert p['dust_amount'] == 0 and p['groove_residue'] == 0
scene.frame_set(1); quality.scene_view(scene)
scene['rolling_collection_ready'] = 'Dirt OFF; dust OFF; groove residue OFF; production quality and defects retained'
studio.save_blend(root/'examples/rolling-shells/Rolling shell capture.blend')
folder = capture.launch(scene, autonomous=True)
studio.save_blend(root/'examples/rolling-shells/Rolling shell capture.blend')
report = dict(passed=True, dirt_enabled=False, dust_amount=0, groove_residue=0,
    defects_unchanged=True, target_images=config.collection_target, folder=str(folder),
    previous_collection=str(previous), previous_collection_stopped=True)
studio.atomic_json(root/'examples/rolling-shells/clean-collection.json', report)
studio.atomic_json(previous/'replaced-by-clean-collection.json', dict(folder=str(folder), reason='User turned dirt off'))
print('DIRT_OFF_COLLECTION_STARTED', json.dumps(report), flush=True)
