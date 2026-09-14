from pathlib import Path
import sys,json
import bpy
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
from shell_appearance import appearance_settings
studio.register();scene=bpy.context.scene;studio.configure_renderer(scene)
folder=root/'examples/polymer-finish-study'
base=studio.settings_dict(scene.pipe_studio)
for name,finish in [('restrained',dict(plastic_roughness=.31,plastic_specular=.30,plastic_coat=.01,crimp_roughness=.23,plastic_finish_variation=.6)),
                    ('balanced',dict(plastic_roughness=.33,plastic_specular=.34,plastic_coat=.01,crimp_roughness=.25,plastic_finish_variation=.6))]:
    studio.apply_settings(scene,{**base,**appearance_settings('REFERENCE'),**finish,'inspection_softness':.55,'texture_strength':.56,'samples':32})
    scene.render.filepath=str(folder/(name+'.png'));bpy.ops.render.render(write_still=True)
    studio.atomic_json(folder/(name+'.json'),studio.settings_dict(scene.pipe_studio))
    print('FINISH_TUNED',name,flush=True)
