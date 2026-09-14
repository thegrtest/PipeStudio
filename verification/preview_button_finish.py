from pathlib import Path
import sys
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
studio.register();scene=bpy.context.scene
studio.apply_settings(scene,dict(defect='NONE',resolution=1600,samples=64,flashlight_camera='FRONT_45'))
r=scene.render;r.use_border=True;r.use_crop_to_border=True
r.border_min_x=.027;r.border_max_x=.19;r.border_min_y=0;r.border_max_y=.325
for value in (.28,.36,.44):
    for obj in scene.objects:
        if obj.get('inspection_region')=='BRASS_FACE':
            rough=obj.data.materials[2].node_tree.nodes['Button polishing roughness']
            rough.inputs['To Min'].default_value=value*.85;rough.inputs['To Max'].default_value=value*1.2
    r.filepath=str(root/'examples'/'button-detail'/f'finish_{value:.2f}.png')
    bpy.ops.render.render(write_still=True)
