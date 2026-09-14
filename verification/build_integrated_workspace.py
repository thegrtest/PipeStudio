"""Build the distributed workspace from the existing brass reference scene."""
from pathlib import Path
import sys
import bpy
root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pipe_studio as studio
studio.register()
scene=bpy.context.scene
if 'PS_Pipe' not in bpy.data.objects:
    studio.setup_scene(scene)
studio.configure_renderer(scene)
studio.refresh(scene,geometry=True)
scene.pipe_studio.product_mode='FLASHLIGHT'
studio.apply_settings(scene,{'flashlight_layout':'MIXED','resolution':1536,'samples':64,'position':.55,'angle':90.,'depth':.18})
folder=root/'examples'/'inspection-modes'
folder.mkdir(exist_ok=True)
info=studio.export_frame(scene,folder,'flashlight_workspace')
studio.atomic_json(folder/'manifest.json',dict(classes={'0':'plastic_dent','1':'metal_dent','2':'metal_scratch'},images=[info],samples=[info]))
scene.name='Inspection Studio'
studio.arrange_view()
studio.save_blend(folder/'Inspection Studio.blend')
print('INTEGRATED_WORKSPACE_BUILT',flush=True)
