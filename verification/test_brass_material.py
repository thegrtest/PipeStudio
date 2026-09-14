import json
from pathlib import Path
import sys
import bpy

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
import pipe_studio as studio
from brass_material import build_brass, update_brass

studio.register()
scene=studio.fresh_scene()
studio.setup_scene(scene)
preset='GODSLIGHT' if '--horizontal' in sys.argv else 'MACHINE'
studio.apply_settings(scene,{**studio.SCENE_PRESETS[preset],'resolution':960,'samples':96,'sensor_noise':0})
mat=bpy.data.materials['PS_Brass']
build_brass(mat)
update_brass(mat,scene.pipe_studio)
assert mat['pipe_brass_version']==2
assert len(mat.node_tree.nodes)>30
assert mat.node_tree.nodes['BrassShader'].inputs['Metallic'].default_value==1
scene.render.filepath=str(ROOT/'verification'/('material-v2-'+preset.lower()+'.png'))
bpy.ops.render.render(write_still=True)
(ROOT/'verification'/'material-v2-test.json').write_text(json.dumps({'passed':True,'nodes':len(mat.node_tree.nodes),'image':scene.render.filepath}),encoding='utf8')
print('BRASS_MATERIAL_VERIFIED',flush=True)
