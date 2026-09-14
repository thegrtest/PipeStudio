from pathlib import Path
import json,sys
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
studio.register();scene=bpy.context.scene
def properties(owner,names):
    return {name:getattr(owner,name) for name in names if hasattr(owner,name)}
info=dict(settings=studio.settings_dict(scene.pipe_studio),
    rolling={p.identifier:getattr(scene.rolling_capture,p.identifier) for p in scene.rolling_capture.bl_rna.properties if p.identifier!='rna_type'},
    render=properties(scene.render,['resolution_x','resolution_y','use_motion_blur','motion_blur_shutter','filter_size']),
    cycles=properties(scene.cycles,['samples','adaptive_threshold','adaptive_min_samples','denoiser','denoising_prefilter','denoising_quality','pixel_filter_type','filter_width']),
    viewport=[dict(type=a.spaces.active.shading.type,scene_lights=a.spaces.active.shading.use_scene_lights,
        scene_world=a.spaces.active.shading.use_scene_world) for s in bpy.data.screens for a in s.areas if a.type=='VIEW_3D'])
out=root/'verification/rolling-quality';out.mkdir(exist_ok=True)
(out/'before-settings.json').write_text(json.dumps(info,indent=2))
print(json.dumps({key:value for key,value in info.items() if key not in ('settings','rolling')},indent=2),flush=True)
