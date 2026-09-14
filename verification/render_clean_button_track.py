"""Render the clean reference through the actual synthetic capture exporter."""
from pathlib import Path
import sys
import shutil
import bpy
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track

def capture(scene,folder):
    scene.camera=next(o for o in scene.objects if o.get('inspection_camera')=='FRONT_45')
    target=folder/'clean-reference'
    info=button_track.export_frame(scene,target,'front_45',studio.settings_dict(scene.pipe_studio))
    assert not info['annotations']
    button_track.write_region_dataset(target,[info])
    studio.atomic_json(target/'manifest.json',dict(classes=dict(enumerate(button_track.CLASSES)),images=[info],samples=[info]))
    shutil.copy2(target/info['image'],folder/'clean_front_45.png')
    render=scene.render
    state=(render.use_border,render.use_crop_to_border,render.border_min_x,render.border_max_x,
           render.border_min_y,render.border_max_y,render.filepath)
    try:
        # Inspection-only detail render; dataset masks retain full-frame coordinates.
        render.use_border=True;render.use_crop_to_border=True
        render.border_min_x=0;render.border_max_x=1;render.border_min_y=0;render.border_max_y=.43
        render.filepath=str(folder/'crimp_detail.png')
        bpy.ops.render.render(write_still=True)
    finally:
        (render.use_border,render.use_crop_to_border,render.border_min_x,render.border_max_x,
         render.border_min_y,render.border_max_y,render.filepath)=state
    return info

if __name__=='__main__':
    studio.register()
    scene=bpy.context.scene
    studio.apply_settings(scene,{'defect':'NONE'})
    capture(scene,root/'examples'/'button-track')
    print('CLEAN_CAPTURE_COMPLETE',flush=True)
