"""Headless Blender verification of camera compositor and mask isolation."""
from pathlib import Path
import json
import sys
import bpy
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from camera_response import configure_camera_response, set_diagnostic_mode

scene = bpy.context.scene
scene.render.engine = 'CYCLES'
scene.cycles.samples = 1
scene.cycles.use_denoising = False
scene.render.resolution_x = scene.render.resolution_y = 128
scene.render.resolution_percentage = 100
scene.render.image_settings.file_format = 'OPEN_EXR'
scene.render.image_settings.color_mode = 'RGBA'
scene.render.image_settings.color_depth = '32'
scene.render.film_transparent = True
folder = ROOT / 'verification' / 'camera-response'
folder.mkdir(exist_ok=True)
settings = {'environment': 'MACHINE', 'resolution': 1600}
assert configure_camera_response(scene, settings)
tree = scene.compositing_node_group
assert configure_camera_response(scene, settings)
assert scene.compositing_node_group == tree and len(tree.nodes) == 4
set_diagnostic_mode(scene, True)
set_diagnostic_mode(scene, True)
configure_camera_response(scene, settings)
assert not scene.render.use_compositing
set_diagnostic_mode(scene, False)
assert scene.render.use_compositing
scene.render.use_compositing = False
set_diagnostic_mode(scene, True)
set_diagnostic_mode(scene, False)
assert not scene.render.use_compositing
scene.render.use_compositing = True

pattern = np.zeros((128, 128, 4), dtype=np.float32)
pattern[:, 64:, :3] = 1
pattern[90:94, 20:24, :3] = 16
pattern[:, :, 3] = 1
test_image = bpy.data.images.new('PS_CR_Verification', width=128, height=128, float_buffer=True)
test_image.pixels.foreach_set(pattern.ravel())
test_image.update()
source = tree.nodes.new('CompositorNodeImage')
source.image = test_image
tree.links.new(source.outputs['Image'], tree.nodes['PS_CR_Lens'].inputs['Image'])

def render(stem):
    path = folder / (stem + '.exr')
    scene.render.filepath = str(path)
    bpy.ops.render.render(write_still=True)
    result = bpy.data.images.load(str(path), check_existing=False)
    pixels = np.array(result.pixels[:], dtype=np.float32).reshape(128, 128, 4)
    bpy.data.images.remove(result)
    return pixels

configure_camera_response(scene, {'environment': 'STUDIO', 'resolution': 1600})
baseline = render('optics-bypassed')
assert np.max(np.abs(baseline - pattern)) < 1e-5
configure_camera_response(scene, settings)
beauty = render('optics-enabled')
edge = beauty[20, 60:68, 0].tolist()
if '--probe' in sys.argv:
    for radius in (1.0, 1.5, 2.0, 3.0):
        tree.nodes['PS_CR_Lens'].inputs['Size'].default_value = (radius, radius)
        probe = render('radius-' + str(radius))
        print('RADIUS_PROBE', radius, probe[20, 60:68, 0].tolist())
assert .015 < beauty[20, 63, 0] < .4, edge
assert .6 < beauty[20, 64, 0] < .985, edge
assert beauty[87, 22, 0] > baseline[87, 22, 0]
assert np.max(np.abs(beauty[20:30, 8:24, 0])) < .01
scene.render.use_compositing = False
original_render = render('render-with-compositor-off')
scene.render.use_compositing = True
set_diagnostic_mode(scene, True)
diagnostic = render('diagnostic-render')
assert np.array_equal(original_render, diagnostic)
set_diagnostic_mode(scene, False)
assert scene.render.use_compositing

foreign = bpy.data.node_groups.new('Foreign compositor test', 'CompositorNodeTree')
scene.compositing_node_group = foreign
assert not configure_camera_response(scene, settings)
assert scene.compositing_node_group == foreign and not foreign.nodes
report = {'passed': True, 'edge_profile': edge,
          'scatter_near_bright_region': float(beauty[87, 22, 0]),
          'far_field_max': float(np.max(np.abs(beauty[20:30, 8:24, 0]))),
          'diagnostic_matches_compositor_disabled': True,
          'preserves_existing_compositor': True,
          'restores_previously_disabled_compositor': True}
(folder / 'result.json').write_text(json.dumps(report, indent=2))
print('CAMERA_RESPONSE_RESULT', report)
