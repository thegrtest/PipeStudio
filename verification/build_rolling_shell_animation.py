"""A separate, editable conveyor loop using the existing packed shell assets."""
from pathlib import Path
import json
import math
import sys
import bpy
from mathutils import Matrix

root=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(root))
import pipe_studio as studio

folder=root/'examples/rolling-shells'
folder.mkdir(parents=True,exist_ok=True)
studio.register()
scene=bpy.context.scene
studio.configure_renderer(scene)
# Keep the saved source's camera response, material finish and light colors.
scene.view_settings.view_transform='Standard'
scene.camera=next(obj for obj in scene.objects if obj.get('inspection_camera')=='FRONT_45')
scene.render.resolution_x=1200
scene.render.resolution_y=600
scene.render.resolution_percentage=100
scene.render.fps=24
scene.frame_start=1
scene.frame_end=144
scene.cycles.samples=32
scene.cycles.adaptive_threshold=.025
scene.cycles.use_denoising=True
scene.cycles.use_animated_seed=False
scene.render.use_persistent_data=True
scene.render.use_motion_blur=True
scene.render.motion_blur_shutter=.32
scene.render.image_settings.file_format='PNG'
scene.render.image_settings.color_mode='RGB'

library=bpy.data.collections.new('Source shells - hidden asset library')
scene.collection.children.link(library)
library.hide_render=True
library.hide_viewport=True
sources={index:[] for index in range(6)}
for obj in list(scene.objects):
    if obj.get('inspection_region') and obj.type=='MESH':
        sources[obj['flashlight_id']].append(obj)
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        library.objects.link(obj)
assert all(len(parts)==4 for parts in sources.values())

stream=bpy.data.collections.new('Rolling shell stream')
scene.collection.children.link(stream)
controls=bpy.data.objects.new('LOOP CONTROLS - six second conveyor',None)
stream.objects.link(controls)
controls.empty_display_type='PLAIN_AXES'
controls.empty_display_size=.25
controls['loop_frames']=144
controls['rolling_radius']=.518
controls['instructions']='24 fps; render frames 1-144. Six shell pitches and two full turns per loop. Radius sets travel and spacing together.'
controls.id_properties_ui('loop_frames').update(min=24,max=1440,description='Match the scene end frame to this value')
controls.id_properties_ui('rolling_radius').update(min=.518,max=.8,description='Rim radius; linked to spacing and rolling speed')

def driven(obj,path,index,expression):
    driver=obj.driver_add(path,index).driver
    driver.type='SCRIPTED'
    for name,key in [('r','rolling_radius'),('period','loop_frames')]:
        var=driver.variables.new()
        var.name=name
        var.type='SINGLE_PROP'
        var.targets[0].id=controls
        var.targets[0].data_path='["'+key+'"]'
    driver.expression=expression

rigs={}
for index in range(-15,16):
    rig=bpy.data.objects.new(f'Rolling shell {index:+03d}',None)
    stream.objects.link(rig)
    rig.empty_display_size=.08
    rig['source_shell']=index%6
    rig['rolling_index']=index
    driven(rig,'location',0,f'({index}-0.5)*2*pi*r/3 + (frame-1)*4*pi*r/period')
    driven(rig,'location',2,'r-0.005')
    driven(rig,'rotation_euler',1,'(frame-1)*4*pi/period')
    rigs[index]=rig
    for original in sources[index%6]:
        obj=original.copy()
        obj.data=original.data
        obj.name=f'Stream {index:+03d} - {original["inspection_region"]}'
        stream.objects.link(obj)
        obj.parent=rig
        obj.matrix_parent_inverse=Matrix.Identity(4)
        obj.location=(0,0,0)
        obj.hide_render=False
        obj.hide_viewport=False
        obj.hide_set(False)

for obj in scene.objects:
    if obj.name.startswith(('Continuous track UNDER','Edge guide rail','Inspection reflection apron')):
        obj.dimensions.x=40

# Assert the central train meets its next repeated copy at the loop boundary.
scene.frame_set(1)
start={index:rig.matrix_world.copy() for index,rig in rigs.items()}
scene.frame_set(145)
error=0.
for index in range(-8,3):
    error=max(error,max(abs(rigs[index].matrix_world[row][column]-start[index+6][row][column])
        for row in range(4) for column in range(4)))
assert error<1e-4,error
assert all(rigs[index]['source_shell']==rigs[index+6]['source_shell'] for index in range(-8,3))
scene.frame_set(1)
scene['animation_loop']='6 seconds / 24 fps / 144 frames; six shell pitches, two full turns; off-camera repeated shell stream.'
scene['animation_source_blend']=bpy.data.filepath
scene['animation_roll_without_slip']=True
scene.render.filepath=str(folder/'frames'/'shell_')
studio.arrange_view()
for screen in bpy.data.screens:
    for area in screen.areas:
        if area.type=='VIEW_3D':
            area.spaces.active.shading.type='MATERIAL'
            area.spaces.active.overlay.show_overlays=False
studio.save_blend(folder/'Infinite shell conveyor.blend')
studio.atomic_json(folder/'animation.json',dict(frames=144,fps=24,duration_seconds=6,width=1200,height=600,
    samples=32,camera='FRONT_45',rolling_radius=.518,shell_pitch=2*math.pi*.518/3,
    travel_per_loop=4*math.pi*.518,rotations_per_loop=2,source_variants=6,
    instantiated_shells=len(rigs),loop_transform_error=error,device=scene.get('pipe_device'),
    source_blend=scene['animation_source_blend']))
scene.render.filepath=str(folder/'preview.png')
bpy.ops.render.render(write_still=True)
print('ROLLING_SHELL_ANIMATION_READY',flush=True)
