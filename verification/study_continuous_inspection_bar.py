from pathlib import Path
import sys,json
import bpy
from mathutils import Vector
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
studio.register();scene=bpy.context.scene;studio.configure_renderer(scene)
folder=root/'examples/reference-recovery'
base=json.loads((folder/'upper-light.json').read_text())['parameters']
studio.apply_settings(scene,base)
for name,y,z,power,size_y in [('continuous-soft',1.8,2.15,300.,.32),('continuous-bright',1.8,2.15,550.,.32),('continuous-far',2.7,2.8,850.,.6)]:
    track.configure(scene,base)
    for obj in scene.objects:
        if obj.type=='LIGHT':
            if obj.name.startswith('Top edge reflection'):
                obj.location=(0,y,z);obj.data.size=7.5;obj.data.size_y=size_y;obj.data.energy=power
            elif obj.name.startswith(('Rib reflection','Broad inspection')):
                obj.data.energy=0 if obj.name.startswith('Rib reflection') else 20.
            elif obj.name.startswith('Right grazing'):obj.data.energy=25.
            obj.rotation_euler=(Vector((0,0,.505))-obj.location).to_track_quat('-Z','Y').to_euler()
        if obj.name.startswith('Inspection reflection apron'):
            shader=obj.data.materials[0].node_tree.nodes.get('Principled BSDF')
            shader.inputs['Base Color'].default_value=(.008,.011,.008,1)
            shader.inputs['Metallic'].default_value=0;shader.inputs['Roughness'].default_value=.15
            shader.inputs['Coat Weight'].default_value=.10
    scene.render.filepath=str(folder/(name+'.png'));bpy.ops.render.render(write_still=True)
    print('CONTINUOUS_BAR_CANDIDATE',name,flush=True)
