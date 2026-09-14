"""A/B dust rendering: changed appearance, identical geometry/region labels."""
from pathlib import Path
import sys
import bpy
import numpy as np
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track
studio.register();scene=bpy.context.scene
folder=root/'examples'/'dust-study';folder.mkdir(exist_ok=True)
infos=[]
for amount,stem in [(0,'without_dust'),(.22,'light_dust')]:
    studio.apply_settings(scene,dict(defect='NONE',dust_amount=amount,resolution=1200,samples=64,
        flashlight_camera='FRONT_45',flashlight_capture='ALL',seed=42))
    info=button_track.export_frame(scene,folder,stem,studio.settings_dict(scene.pipe_studio))
    assert not info['annotations'] and info['visible_mask_pixels']==0
    infos.append(info)
assert infos[0]['recipe']==infos[1]['recipe'],'Dust altered geometry recipe'
for a,b in zip(infos[0]['region_annotations'],infos[1]['region_annotations']):
    images=[bpy.data.images.load(str(folder/c['mask']),check_existing=False) for c in (a,b)]
    arrays=[np.array(im.pixels[:]) for im in images]
    assert np.array_equal(*arrays),'Dust altered a region mask'
    for im in images:bpy.data.images.remove(im)
button_track.write_region_dataset(folder,infos)
studio.atomic_json(folder/'manifest.json',dict(classes=dict(enumerate(button_track.CLASSES)),images=infos,samples=infos))
studio.atomic_json(folder/'dust-checks.json',dict(passed=True,region_masks_identical=True,defect_labels_empty=True,dust_amount=.22))
studio.apply_settings(scene,{'defect':'OPEN_CENTER','flashlight_layout':'SINGLE','flashlight_index':1})
studio.arrange_view();studio.save_blend(root/'examples'/'button-track'/'Brass Button Track.blend')
print('DUST_STUDY_VERIFIED',flush=True)
