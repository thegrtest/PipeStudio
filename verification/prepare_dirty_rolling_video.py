"""Save the collection appearance and a separate seamless twelve-specimen film."""
from pathlib import Path
import copy
import json
import math
import sys
import bpy
from mathutils import Matrix

root = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(root))
import pipe_studio as studio
import rolling_capture as capture
import rolling_quality as quality
import rolling_randomization as randomization

studio.register(); scene = bpy.context.scene
transform = scene.view_settings.view_transform
studio.configure_renderer(scene); scene.view_settings.view_transform = transform
config = scene.rolling_capture
config.production_quality = True; config.resolution = 2400; config.samples = 192
config.mix_soiling = True; config.dirty_fraction = .5; config.dirt_strength = 1.
config.random_seed = 61000; config.randomize_defects = True
config.body_dents = 4; config.twist_limit = 12
config.start = 1; config.end = 144; config.step = 12
config.camera = 'ALL'; config.trigger = 'DEFECT'
config.collection_target = 3000; config.collection_pass_limit = 1000
p = quality.configure(scene, {**quality.PRODUCTION, **capture.quality_options(config)})
rigs, source, spec = randomization.randomize(scene, p, capture.random_options(config))
quality.scene_view(scene)
scene.frame_set(1)
scene.camera = next(o for o in scene.objects if o.get('inspection_camera') == 'FRONT_45')
scene['rolling_quality_version'] = 1
scene['rolling_collection_ready'] = 'Production capture, mixed clean and heavily dirty shells, dirt is normal appearance'
studio.save_blend(root / 'examples/rolling-shells/Rolling shell capture.blend')

folder = root / 'examples/rolling-shells/dirty-defect-loop'
folder.mkdir(exist_ok=True)
templates = {rig['rolling_index'] % 12: rig for rig in rigs[:12]}
items = {rig['rolling_index'] % 12: item for rig, item in zip(rigs[:12], spec['items'][:12])}
collection = next(iter(rigs[0].users_collection))
controls = next(o for o in scene.objects if 'loop_frames' in o)
controls['loop_frames'] = 72
controls['instructions'] = 'Render frames 1-144 at 24 fps. Twelve specimen variants, four full turns, seamless repeated stream.'
controls.update_tag()
bpy.context.view_layer.update()

def driven(obj, path, index, expression):
    driver = obj.driver_add(path, index).driver; driver.type = 'SCRIPTED'
    for name, key in [('r', 'rolling_radius'), ('period', 'loop_frames')]:
        var = driver.variables.new(); var.name = name; var.type = 'SINGLE_PROP'
        var.targets[0].id = controls; var.targets[0].data_path = '["' + key + '"]'
    driver.expression = expression

new_rigs = {}
for index in range(-21, 16):
    template = templates[index % 12]
    rig = bpy.data.objects.new(f'Video rolling specimen {index:+03}', None)
    collection.objects.link(rig)
    rig['rolling_index'] = index; rig['source_shell'] = index % 12
    rig['normal_appearance'] = json.dumps(items[index % 12]['normal_appearance'])
    driven(rig, 'location', 0, f'({index}-.5)*2*pi*r/3+(frame-1)*4*pi*r/period')
    driven(rig, 'location', 2, 'r-.005')
    driven(rig, 'rotation_euler', 1, '(frame-1)*4*pi/period')
    for original in template.children:
        obj = original.copy(); obj.data = original.data
        collection.objects.link(obj); obj.parent = rig
        obj.matrix_parent_inverse = Matrix.Identity(4); obj.location = (0, 0, 0)
        obj.name = f'Video {index:+03} | ' + original.get('inspection_region', 'aperture')
    new_rigs[index] = rig
for rig in rigs:
    for child in list(rig.children): bpy.data.objects.remove(child, do_unlink=True)
    bpy.data.objects.remove(rig, do_unlink=True)
for mesh in list(bpy.data.meshes):
    if mesh.users == 0: bpy.data.meshes.remove(mesh)
for mat in list(bpy.data.materials):
    if mat.get('rolling_generated') and mat.users == 0: bpy.data.materials.remove(mat)

scene.frame_set(1); bpy.context.view_layer.update()
start = {i: rig.matrix_world.copy() for i, rig in new_rigs.items()}
scene.frame_set(145); bpy.context.view_layer.update()
error = max(abs(new_rigs[i].matrix_world[row][col] - start[i+12][row][col])
            for i in range(-15, 0) for row in range(4) for col in range(4))
print('LOOP_CHECK', controls.name, controls['loop_frames'], list(start[-3].translation),
      list(new_rigs[-15].matrix_world.translation), error, flush=True)
assert error < 1e-4, error
for i in range(-15, 0):
    assert new_rigs[i]['normal_appearance'] == new_rigs[i+12]['normal_appearance']
scene.frame_set(1); scene.frame_start = 1; scene.frame_end = 144
scene.render.fps = 24; scene.render.use_motion_blur = False
scene.render.image_settings.file_format = 'PNG'; scene.render.image_settings.color_mode = 'RGB'
scene.render.use_persistent_data = True
scene.cycles.use_animated_seed = False
scene['animation_loop'] = 'Six seconds, 12 distinct dirty/clean specimens, seamless video loop'
scene['video_only'] = True
studio.save_blend(folder / 'Dirty defect conveyor.blend')
report = dict(frames=144, fps=24, duration_seconds=6, width=2400, height=1200, samples=192,
    distinct_variants=12, instantiated_shells=37, loop_transform_error=error,
    appearance_counts={name: sum(item['normal_appearance']['category']==name for item in items.values())
                       for name in ('clean', 'light', 'heavy')},
    quality=quality.PRODUCTION, specimens=list(items.values()),
    note='The video repeats twelve variants seamlessly. Dataset collection generates fresh unique shells per pass.')
studio.atomic_json(folder / 'video.json', report)
scene.render.filepath = str(folder / 'preview.png')
bpy.ops.render.render(write_still=True)
print('DIRTY_ROLLING_VIDEO_READY', json.dumps(report['appearance_counts']), flush=True)
