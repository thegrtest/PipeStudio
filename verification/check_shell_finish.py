"""Same specimen row under reference and clean finish, with mask invariance."""
from pathlib import Path
import sys,json,hashlib
import bpy
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
import button_row
from shell_appearance import appearance_settings

studio.register();scene=bpy.context.scene
folder=root/'examples/polymer-finish-study';folder.mkdir(exist_ok=True)
original=json.loads(scene['flashlight_recipe'])
base=studio.settings_dict(scene.pipe_studio)
studio.configure_renderer(scene)

def geometry_hashes():
    hashes={}
    for obj in scene.objects:
        if obj.get('inspection_region'):
            coords=np.empty(len(obj.data.vertices)*3,dtype=np.float32)
            obj.data.vertices.foreach_get('co',coords)
            slots=np.empty(len(obj.data.polygons),dtype=np.int32)
            obj.data.polygons.foreach_get('material_index',slots)
            hashes[(obj['flashlight_id'],obj['inspection_region'])]=hashlib.sha256(coords.tobytes()+slots.tobytes()).hexdigest()
    return hashes

infos=[];hashes=None;region_masks=None;defect_masks=None
for profile in ('REFERENCE','CLEAN'):
    studio.apply_settings(scene,{**base,**appearance_settings(profile),'resolution':1200,'samples':64,
                                'flashlight_camera':'REFERENCE','flashlight_capture':'CURRENT'})
    # Exercise the actual sidebar operator, not just direct preset dictionaries.
    assert bpy.ops.pipe.shell_appearance(preset=profile)=={'FINISHED'}
    p=studio.settings_dict(scene.pipe_studio)
    assert json.loads(scene['flashlight_recipe'])['items']==original['items']
    assert len([d for d in original['defects'] if d['kind']=='plastic_dent' and d['region']=='BODY'])==4
    if hashes is None:hashes=geometry_hashes()
    else:assert hashes==geometry_hashes(),'Appearance changed geometry or labeled faces'
    info=track.export_frame(scene,folder/profile.lower(),profile.lower(),p);infos.append(info)
    track.write_region_dataset(folder/profile.lower(),[info])
    studio.atomic_json(folder/profile.lower()/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=[info],samples=[info]))
    # Compare the decoded IDs, including silhouettes and defect boundaries.
    regions=track.mask_pass(scene,folder/profile.lower(),'verify_regions',regions=True)
    defects=track.mask_pass(scene,folder/profile.lower(),'verify_defects')
    if region_masks is None:region_masks,defect_masks=regions,defects
    else:
        assert np.array_equal(regions,region_masks)
        assert np.array_equal(defects,defect_masks)
    assert info['appearance_version']==5
    assert info['parameters']['plastic_roughness']==p['plastic_roughness']
    if profile=='CLEAN':
        tree=scene.compositing_node_group
        assert tree.nodes['PS_CR_Lens'].mute and tree.nodes['PS_CR_Highlights'].mute
        assert p['sensor_noise']==p['dust_amount']==p['groove_residue']==p['finish_marks']==0
    studio.save_blend(folder/('Reference finish.blend' if profile=='REFERENCE' else 'Clean finish.blend'))
    print('FINISH_PROFILE_VERIFIED',profile,flush=True)
studio.atomic_json(folder/'verification.json',dict(passed=True,body_dents=4,
    all_24_region_meshes_identical=True,region_masks_pixel_identical=True,defect_masks_pixel_identical=True,
    presets_preserve_recipe=True,clean_camera_effects_disabled=True))
studio.apply_settings(scene,{**base,**appearance_settings('REFERENCE'),'resolution':1200,'samples':64,
                            'flashlight_camera':'REFERENCE','flashlight_capture':'ALL'})
p=studio.settings_dict(scene.pipe_studio)
standard=track.export_views(scene,folder/'reference','row',p)
assert [i['camera_id'] for i in standard]==list(track.CAMERAS)
all_views=[infos[0],*standard]
track.write_region_dataset(folder/'reference',all_views)
studio.atomic_json(folder/'reference'/'manifest.json',dict(classes=dict(enumerate(track.CLASSES)),images=all_views,samples=all_views))
scene.camera=next(o for o in scene.objects if o.get('inspection_camera')=='REFERENCE')
studio.arrange_view()
studio.save_blend(folder/'Reference finish.blend')
studio.save_blend(root/'examples/button-track/Brass Button Track.blend')
# Keep the existing local edit behavior after swapping materials.
old=json.loads(scene['flashlight_recipe'])
index=button_row.mutate(scene,p)
new=json.loads(scene['flashlight_recipe'])
assert [i for i,(a,b) in enumerate(zip(old['items'],new['items'])) if a!=b]==[index]
assert sum(d['region']=='BODY' and d['kind']=='plastic_dent' for d in new['defects'])==4
print('SHELL_FINISH_VERIFIED',flush=True)
