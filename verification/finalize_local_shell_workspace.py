"""Verify saved local edits after reopening and restore the normal export folder."""
import json
from pathlib import Path
import bpy
import pipe_studio as studio
root=Path(__file__).resolve().parents[1];scene=bpy.context.scene
expected=json.loads((root/'examples/local-shell-updates/after/metadata/row_front_45.json').read_text())['recipe']
assert json.loads(scene['flashlight_recipe'])==expected,'Reopening lost the edited row'
assert scene['button_row_defective_count']==5 and scene['button_row_next_index']==1
scene.pipe_studio.output_dir=str(root/'exports')+'/'
studio.save_blend(root/'examples/button-track/Brass Button Track.blend')
studio.atomic_json(root/'examples/local-shell-updates/reopen-check.json',dict(passed=True,
    row_revision=expected['row_revision'],defective_shells=scene['button_row_defective_count'],
    next_shell=scene['button_row_next_index']+1))
print('LOCAL_ROW_REOPEN_VERIFIED',flush=True)
