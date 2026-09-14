"""Image-guided light placement with the same row and revised glossy polymer."""
from pathlib import Path
import sys,json
import bpy
from mathutils import Vector
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root))
import pipe_studio as studio
import button_track as track
studio.register();scene=bpy.context.scene;studio.configure_renderer(scene)
folder=root/'examples/reference-recovery';folder.mkdir(exist_ok=True)
original=json.loads(scene['flashlight_recipe'])
base={**studio.settings_dict(scene.pipe_studio),
      'plastic_roughness':.24,'plastic_specular':.45,'plastic_coat':.055,
      'plastic_finish_variation':.28,'groove_polish':.72,'groove_residue':.4,
      'crimp_roughness':.185,'plastic_ink_wear':.62,'dust_amount':.16,'finish_marks':.48,
      'texture_strength':.56,'inspection_softness':.5,'sensor_noise':.0075,
      'flashlight_camera':'REFERENCE','flashlight_capture':'CURRENT','resolution':960,'samples':32}
studio.apply_settings(scene,base)
assert json.loads(scene['flashlight_recipe'])['items']==original['items']
cases=[('earlier-gloss',dict(key_power=1500.,rim_power=1500.,fill_power=145.,key_angle=45.),.7),
       ('upper-light',dict(key_power=400.,rim_power=1800.,fill_power=145.,key_angle=45.),.45),
       ('near-upper-light',dict(key_power=200.,rim_power=1800.,fill_power=125.,key_angle=40.),.35),
       ('balanced-close',dict(key_power=700.,rim_power=1400.,fill_power=130.,key_angle=45.),.4)]
for name,settings,distance in cases:
    p={**base,**settings};track.configure(scene,p)
    for obj in scene.objects:
        if obj.type=='LIGHT' and obj.name.startswith(('Broad inspection','Top edge reflection','Rib reflection')):
            factor=distance/.7
            obj.location.y*=factor;obj.location.z=.505+(obj.location.z-.505)*factor
            obj.data.energy*=factor**2;obj.data.size*=factor;obj.data.size_y*=factor
            aim_x=obj.location.x if obj.get('inspection_rib_light') else 0
            obj.rotation_euler=(Vector((aim_x,0,.4))-obj.location).to_track_quat('-Z','Y').to_euler()
        if obj.name.startswith('Inspection reflection apron') and name!='earlier-gloss':
            shader=obj.data.materials[0].node_tree.nodes.get('Principled BSDF')
            shader.inputs['Base Color'].default_value=(.008,.011,.008,1)
            shader.inputs['Metallic'].default_value=0;shader.inputs['Roughness'].default_value=.15
            shader.inputs['Coat Weight'].default_value=.10
    scene.render.filepath=str(folder/(name+'.png'));bpy.ops.render.render(write_still=True)
    studio.atomic_json(folder/(name+'.json'),dict(parameters=p,fixture_distance=distance))
    print('REFERENCE_RECOVERY_CANDIDATE',name,flush=True)
