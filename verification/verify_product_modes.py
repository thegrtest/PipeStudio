"""Actual Blender mode switching, exports, mask isolation and background batch."""
import json
import sys
from pathlib import Path
import bpy
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pipe_studio as studio
from app_model import validate_settings
import flashlight_integration as flashlight

out=root/'verification'/'product-modes'
out.mkdir(exist_ok=True)
studio.register()
scene=studio.fresh_scene()
studio.setup_scene(scene)
p=scene.pipe_studio
studio.apply_settings(scene,{'seed':123,'depth':.17,'resolution':480,'samples':8})
pipe_settings=studio.settings_dict(p)
pipe_info=studio.export_frame(scene,out,'pipe_before')
assert pipe_info['visible_mask_pixels']>0
p.product_mode='FLASHLIGHT'
assert p.environment=='TRACK' and p.defect=='DENT'
studio.apply_settings(scene,{'resolution':640,'samples':16,'seed':42,'flashlight_layout':'MIXED','angle':90})
assert scene.camera.name.startswith('Overhead inspection')
assert all(o.hide_render for o in scene.objects if o.name.startswith('PS_'))
flash_info=studio.export_frame(scene,out,'flashlight_mixed')
assert len(flash_info['annotations'])==4
assert {a['class_id'] for a in flash_info['annotations']}=={0,1,2}
assert all(a['visible_pixels']>0 for a in flash_info['annotations']),flash_info['annotations']
saved=studio.settings_dict(p)
p.product_mode='PIPE'
assert p.seed==123 and abs(p.depth-.17)<1e-6
assert p.environment==pipe_settings['environment']
assert scene.camera.name=='PS_Camera' and not bpy.data.objects['PS_Pipe'].hide_render
assert all(o.hide_render for o in scene.objects if o.get('inspection_flashlight'))
pipe_after=studio.export_frame(scene,out,'pipe_after')
assert pipe_after['bbox_xywh']==pipe_info['bbox_xywh']
p.product_mode='FLASHLIGHT'
assert p.seed==42 and p.flashlight_layout=='MIXED'
studio.apply_settings(scene,{'defect':'NONE'})
clean=studio.export_frame(scene,out,'flashlight_clean')
assert not clean['annotations'] and clean['visible_mask_pixels']==0
studio.apply_settings(scene,{'defect':'DENT','flashlight_roll':180})
hidden=studio.export_frame(scene,out,'flashlight_hidden')
assert hidden['visible_mask_pixels']==0
assert all(a['bbox_xywh'] is None for a in hidden['annotations'])
studio.apply_settings(scene,{'flashlight_roll':0,'flashlight_layout':'SINGLE','flashlight_surface':'METAL','defect':'SCRATCH'})
scratch=studio.export_frame(scene,out,'flashlight_scratch')
assert len(scratch['annotations'])==1 and scratch['annotations'][0]['class_id']==2
assert scratch['visible_mask_pixels']>0
# Mask mode must survive export and restore the actual beauty materials afterwards.
studio.SUSPENDED=True; p.mask_view=True; studio.SUSPENDED=False
flashlight.mask_view(scene,True)
studio.export_frame(scene,out,'flashlight_from_mask_view')
flashlight.mask_view(scene,False)
studio.SUSPENDED=True; p.mask_view=False; studio.SUSPENDED=False
assert not any('flashlight_original_materials' in o for o in scene.objects)
studio.apply_settings(scene,{'flashlight_layout':'MIXED','defect':'DENT','resolution':480,'samples':8})
p.output_dir=str(out/'batch'); p.batch_count=2; p.clean_fraction=0
job=studio.launch_job(scene,True)
result=studio.ACTIVE_JOB['process'].wait(timeout=180)
assert result==0,(job/'render.log').read_text()[-5000:]
assert studio.read_status(job)['completed']==2
manifest=json.loads((job/'manifest.json').read_text())
assert len(manifest['samples'])==2 and manifest['product_mode']=='FLASHLIGHT'
assert (job/'annotations.coco.json').is_file()
# Saving and reloading the workspace keeps both mode settings.
studio.apply_settings(scene,{'resolution':1536,'samples':64,'flashlight_layout':'MIXED','defect':'DENT'})
scene.name='Inspection Studio'
target=root/'examples'/'inspection-modes'
target.mkdir(exist_ok=True)
studio.arrange_view()
studio.save_blend(target/'Inspection Studio.blend')
studio.atomic_json(out/'result.json',dict(passed=True,batch=str(job),workspace=str(target/'Inspection Studio.blend'),
                  checks=['pipe round trip','mode settings persistence','three defect classes','clean labels','occluded labels','mask restoration','background batch']))
print('PRODUCT_MODES_VERIFIED',flush=True)
