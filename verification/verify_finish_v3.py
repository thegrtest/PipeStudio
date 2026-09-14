"""Run with Blender -b --factory-startup --python verification/verify_finish_v3.py."""
import json
import math
import os
from pathlib import Path
import sys

import bpy
from mathutils import Vector
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from brass_material import build_brass, update_brass
from geometry import PipeSpec, build_mesh

OUT = ROOT / 'verification' / 'finish-v3'
OUT.mkdir(parents=True, exist_ok=True)
os.environ['OPTIX_CACHE_PATH'] = str(ROOT / '.cache' / 'optix')
bpy.context.preferences.use_preferences_save = False
scene = bpy.context.scene
for obj in list(scene.objects):
    bpy.data.objects.remove(obj, do_unlink=True)
scene.render.engine = 'CYCLES'
scene.cycles.samples = 48
scene.cycles.use_denoising = True
scene.cycles.seed = 73
scene.cycles.use_animated_seed = False
scene.cycles.max_bounces = 4
prefs = bpy.context.preferences.addons['cycles'].preferences
try:
    prefs.compute_device_type = 'OPTIX'
    prefs.refresh_devices()
    for device in prefs.devices:
        device.use = device.type == 'OPTIX'
    scene.cycles.device = 'GPU'
except (TypeError, RuntimeError):
    pass
scene.render.resolution_x = 960
scene.render.resolution_y = 512
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'PNG'
scene.view_settings.view_transform = 'AgX'
scene.world.use_nodes = True
scene.world.node_tree.nodes['Background'].inputs['Color'].default_value = (.15, .19, .12, 1)
scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value = .4

spec = PipeSpec(defect='NONE', taper_start=.76, taper_end=.88, end_ratio=.66)
vertices, faces, masks, _ = build_mesh(spec, 96, 96)
mesh = bpy.data.meshes.new('Finish verification pipe')
mesh.from_pydata(vertices, [], faces)
obj = bpy.data.objects.new('Finish verification pipe', mesh)
scene.collection.objects.link(obj)
for polygon in mesh.polygons:
    polygon.use_smooth = True
material = bpy.data.materials.new('Finish verification brass')
build_brass(material)
mesh.materials.append(material)

def aim(obj, target):
    obj.rotation_euler = (Vector(target)-obj.location).to_track_quat('-Z', 'Y').to_euler()

camera = bpy.data.objects.new('Finish camera', bpy.data.cameras.new('Finish camera'))
scene.collection.objects.link(camera)
camera.location = (0, -10, 1.4)
camera.data.lens = 42
aim(camera, (0, 0, 0))
scene.camera = camera
for name, location, power, width, height in (
        ('Key', (0, -4, 4), 850, 6, 1.5), ('Fill', (-2, -2, -2), 200, 4, 2),
        ('Rim', (1, 3, 3), 450, 5, .6)):
    data = bpy.data.lights.new(name, 'AREA')
    data.energy, data.shape, data.size, data.size_y = power, 'RECTANGLE', width, height
    light = bpy.data.objects.new(name, data)
    scene.collection.objects.link(light)
    light.location = location
    aim(light, (0, 0, 0))

settings = dict(roughness=.31, texture_strength=.20, wear=.23, radius=spec.radius,
                finish_marks=0, seed=101)

def socket_snapshot():
    values = {}
    for node in material.node_tree.nodes:
        for i, socket in enumerate(tuple(node.inputs)+tuple(node.outputs)):
            if not hasattr(socket, 'default_value'):
                continue
            value = socket.default_value
            if isinstance(value, (int, float)):
                assert math.isfinite(value), (node.name, socket.name)
                values[f'{node.name}:{i}'] = value
            elif hasattr(value, '__len__') and not isinstance(value, str):
                numeric = tuple(value)
                if all(isinstance(v, (int, float)) for v in numeric):
                    assert all(math.isfinite(v) for v in numeric), (node.name, socket.name)
                    values[f'{node.name}:{i}'] = numeric
    return values

update_brass(material, settings)
zero_snapshot = socket_snapshot()
assert material['pipe_brass_version'] == 3
assert material.node_tree.nodes['Finish marks amount'].outputs[0].default_value == 0
assert not material.node_tree.nodes['Brass output'].inputs['Displacement'].is_linked
coords = material.node_tree.nodes['Seeded finish coordinates']
assert coords.inputs[0].links[0].from_socket.name == 'Object'

update_brass(material, {**settings, 'finish_marks': 1})
one_snapshot = socket_snapshot()
assert material.node_tree.nodes['Finish marks amount'].outputs[0].default_value == 1
update_brass(material, {**settings, 'finish_marks': 1, 'key_power': 999, 'camera_yaw': 55})
assert socket_snapshot() == one_snapshot
obj.rotation_euler.x = .9
update_brass(material, {**settings, 'finish_marks': 1})
assert socket_snapshot() == one_snapshot
obj.rotation_euler.x = 0
update_brass(material, {**settings, 'finish_marks': 1, 'seed': 102})
assert socket_snapshot()['Seeded finish coordinates:1'] != one_snapshot['Seeded finish coordinates:1']
update_brass(material, {**settings, 'finish_marks': float('nan'), 'seed': float('inf')})
socket_snapshot()
assert material.node_tree.nodes['Finish marks amount'].outputs[0].default_value == 0
update_brass(material, settings)
assert socket_snapshot() == zero_snapshot

def render(name):
    path = OUT / (name+'.png')
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    rendered = bpy.data.images.load(str(path), check_existing=False)
    pixels = np.empty(len(rendered.pixels), dtype=np.float32)
    rendered.pixels.foreach_get(pixels)
    bpy.data.images.remove(rendered)
    assert np.isfinite(pixels).all()
    return pixels

zero = render('finish0')
# Bypassing all optional finish branches reconstructs the original v2 color and
# roughness wiring; a pixel match proves zero-control rendering compatibility.
nodes, links = material.node_tree.nodes, material.node_tree.links
links.new(nodes['Fresh metal in drawing marks'].outputs['Color'], nodes['BrassShader'].inputs['Base Color'])
links.new(nodes['Scratch roughness'].outputs[0], nodes['Roughness minimum'].inputs[0])
original = render('v2-baseline')
assert np.max(np.abs(zero-original)) <= 1/255 + 1e-6
build_brass(material)
update_brass(material, {**settings, 'finish_marks': 1})
finished = render('finish1')
changed_fraction = float(np.mean(np.abs(finished-zero) > 2/255))
assert changed_fraction > .003, changed_fraction
assert not any(masks)
assert len(obj.data.vertices) == len(vertices)
result = {'passed': True, 'material_version': 3, 'nodes': len(nodes),
          'zero_vs_v2_max_error': float(np.max(np.abs(zero-original))),
          'finish_changed_fraction': changed_fraction,
          'seed_repeatability': True, 'local_coordinates': True, 'geometry_unchanged': True,
          'images': [str(OUT/(name+'.png')) for name in ('finish0', 'finish1', 'v2-baseline')]}
(OUT/'result.json').write_text(json.dumps(result, indent=2), encoding='utf8')
print('FINISH_V3_VERIFIED', json.dumps(result), flush=True)
