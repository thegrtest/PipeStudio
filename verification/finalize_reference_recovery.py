"""Verify the photo rig and reversible finishes on the preserved four-dent row."""
from pathlib import Path
import sys,json,copy,hashlib
import bpy
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
from shell_appearance import appearance_settings
from shell_lighting import LIGHT_PRESETS
studio.register();scene=bpy.context.scene;studio.configure_renderer(scene)
folder=root/'examples/reference-recovery/final';folder.mkdir(parents=True,exist_ok=True)
original=json.loads(scene['flashlight_recipe'])
base=studio.settings_dict(scene.pipe_studio)
def hashes():
    result={}
    for obj in scene.objects:
        if obj.get('inspection_region'):
            co=np.empty(len(obj.data.vertices)*3,dtype=np.float32);obj.data.vertices.foreach_get('co',co)
            marks=np.empty(len(obj.data.polygons),dtype=np.int32);obj.data.polygons.foreach_get('material_index',marks)
            result[(obj['flashlight_id'],obj['inspection_region'])]=hashlib.sha256(co.tobytes()+marks.tobytes()).hexdigest()
    return result
before=hashes()
p={**base,**appearance_settings('REFERENCE'),**LIGHT_PRESETS['PHOTO'],'resolution':1200,'samples':64,
   'flashlight_camera':'REFERENCE','flashlight_capture':'ALL'}
studio.apply_settings(scene,p)
assert hashes()==before
for profile in ('SATIN','CLEAN','REFERENCE'):
    assert bpy.ops.pipe.shell_appearance(preset=profile)=={'FINISHED'}
    assert json.loads(scene['flashlight_recipe'])['items']==original['items']
    assert hashes()==before
for profile in ('EARLIER','PHOTO'):
    assert bpy.ops.pipe.shell_lighting(preset=profile)=={'FINISHED'}
    assert hashes()==before
p=studio.settings_dict(scene.pipe_studio)
infos=track.export_views(scene,folder,'row',p)
assert [i['camera_id'] for i in infos]==list(track.CAMERAS)
scene.camera=next(o for o in scene.objects if o.get('inspection_camera')=='REFERENCE')
reference=track.export_frame(scene,folder,'row_reference',p);infos.append(reference)
assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in reference['recipe']['defects'])==4
def pixels(path):
    im=bpy.data.images.load(str(path),check_existing=False)
    values=np.empty(len(im.pixels),dtype=np.float32);im.pixels.foreach_get(values)
    bpy.data.images.remove(im);return values
previous=root/'examples/polymer-finish-study/reference'
checked=0
for annotation in reference['region_annotations']+reference['annotations']:
    new=annotation['mask'];old=new.replace('row_reference','reference')
    assert np.array_equal(pixels(folder/new),pixels(previous/old)),new
    checked+=1
assert np.array_equal(pixels(folder/reference['mask']),pixels(previous/'masks/reference.png'))
track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=infos,samples=infos))
studio.arrange_view()
studio.save_blend(root/'examples/reference-recovery/Photo recovery.blend')
studio.save_blend(root/'examples/button-track/Brass Button Track.blend')
old=json.loads(scene['flashlight_recipe']);index=button_row.mutate(scene,p);new=json.loads(scene['flashlight_recipe'])
assert [i for i,(a,b) in enumerate(zip(old['items'],new['items'])) if a!=b]==[index]
assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in new['defects'])==4
# Separate undamaged comparison: keep the same finish, pose and identity.
normal=copy.deepcopy(original)
for item in normal['items']:item['defect']=None
normal['defects']=[];normal['required_body_dents']=0
q={**p,'defect':'NONE','flashlight_capture':'CURRENT'}
button_row.remember(scene,q,normal);studio.apply_settings(scene,q)
clean_folder=root/'examples/reference-recovery/undamaged-comparison'
clean=track.export_frame(scene,clean_folder,'undamaged_reference',q)
assert not clean['annotations'] and clean['visible_mask_pixels']==0
track.write_region_dataset(clean_folder,[clean])
studio.atomic_json(clean_folder/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=[clean],samples=[clean]))
studio.save_blend(root/'examples/reference-recovery/Undamaged photo comparison.blend')
studio.atomic_json(folder/'verification.json',dict(passed=True,body_dents_in_saved_workspace=4,
    all_region_meshes_preserved=True,unchanged_individual_masks=checked,combined_mask_unchanged=True,
    appearance_presets_checked=3,lighting_presets_checked=2,standard_camera_views=3,
    one_shell_update_verified=True,undamaged_comparison_has_empty_defect_labels=True))
print('PHOTO_RECOVERY_VERIFIED',flush=True)
