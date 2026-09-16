"""Restrained inspection-camera response in Blender 5.1's compositor.

This is a visual approximation, not a calibrated lens or sensor model. The
editable PS nodes operate on scene-linear radiance before the view transform;
the exporter may add camera noise after writing the beauty image. Diagnostic
masks must call set_diagnostic_mode(scene, True), then restore it in finally.

Only a compositor graph created by this module is configured. An existing
unrelated compositor is left intact. Diagnostic mode bypasses all compositing
and restores the exact previous render flag, including a previously disabled
compositor. Repeated enable/disable calls are safe.
"""

import bpy
from shell_appearance import POLYMER_DEFAULTS
from domain_profiles import optical_response, optical_reference_width


OWNER = 'pipe_studio_camera_response'
DIAGNOSTIC = '_ps_camera_response_diagnostic'
RESTORE = '_ps_camera_response_restore_compositing'


def _value(settings, key, default):
    return settings.get(key, default) if isinstance(settings, dict) else getattr(settings, key, default)


def _make_graph(scene):
    current = scene.compositing_node_group
    if current is not None:
        if not current.get(OWNER, False):
            scene['pipe_camera_response_status'] = 'Existing user compositor preserved'
            return None
        return current
    tree = bpy.data.node_groups.new('PS_CameraResponse_' + scene.name, 'CompositorNodeTree')
    tree[OWNER] = True
    tree.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    source = tree.nodes.new('CompositorNodeRLayers')
    source.name = 'PS_CR_Source'
    source.label = 'Scene-linear camera image'
    source.scene = scene
    source.location = (-560, 80)
    blur = tree.nodes.new('CompositorNodeBlur')
    blur.name = 'PS_CR_Lens'
    blur.label = 'Optical Gaussian kernel radius (3 x sigma)'
    blur.location = (-290, 80)
    blur.inputs['Type'].default_value = 'Gaussian'
    blur.inputs['Extend Bounds'].default_value = False
    blur.inputs['Separable'].default_value = True
    glare = tree.nodes.new('CompositorNodeGlare')
    glare.name = 'PS_CR_Highlights'
    glare.label = 'Local scatter from very bright highlights'
    glare.location = (-30, 80)
    glare.inputs['Type'].default_value = 'Fog Glow'
    glare.inputs['Quality'].default_value = 'High'
    glare.inputs['Threshold'].default_value = 2.5
    glare.inputs['Smoothness'].default_value = .12
    glare.inputs['Clamp'].default_value = False
    glare.inputs['Saturation'].default_value = 1.0
    glare.inputs['Tint'].default_value = (1, 1, 1, 1)
    output = tree.nodes.new('NodeGroupOutput')
    output.name = 'PS_CR_Output'
    output.label = 'Beauty only - bypass for masks'
    output.location = (260, 80)
    output.is_active_output = True
    tree.links.new(source.outputs['Image'], blur.inputs['Image'])
    tree.links.new(blur.outputs['Image'], glare.inputs['Image'])
    tree.links.new(glare.outputs['Image'], output.inputs['Image'])
    scene.compositing_node_group = tree
    return tree


def configure_camera_response(scene, settings):
    """Configure a subtle editable response, preserving unrelated node trees.

    Settings accepts either a dictionary or Pipe Studio's property group.
    STUDIO passes through unless extra camera softness is requested. Presets retain their framing;
    the graph has no distortion, crop, resampling, or vignette operations.
    """
    tree = _make_graph(scene)
    if tree is None:
        return False
    environment = _value(settings, 'environment', 'STUDIO')
    resolution = max(1, int(_value(settings, 'resolution', scene.render.resolution_x)))
    inspection = environment in {'MACHINE', 'GODSLIGHT','BUTTON_TRACK'}
    reference_width = optical_reference_width(settings)
    response = optical_response(settings)
    nominal_sigma = response['total_sigma_at_reference']
    extra = response['extra_sigma_at_reference']
    enabled = inspection or extra>0
    if environment=='BUTTON_TRACK':
        nominal_sigma=_value(settings,'inspection_softness',POLYMER_DEFAULTS['inspection_softness'])
    sigma = nominal_sigma * resolution / reference_width
    blur = tree.nodes.get('PS_CR_Lens')
    glare = tree.nodes.get('PS_CR_Highlights')
    if blur is None or glare is None:
        scene['pipe_camera_response_status'] = 'Edited camera graph preserved; PS nodes missing'
        return False
    # Blender 5.1 Gaussian Size is approximately a 3-sigma support radius.
    # Tested on a unit step: Size=1.5 gives ~10.7% adjacent-pixel leakage,
    # consistent with sigma=.5 px. Size=.5 has effectively no optical effect.
    blur.inputs['Size'].default_value = (sigma * 3, sigma * 3)
    blur.mute = not enabled or sigma<=0
    scatter=_value(settings,'inspection_scatter',.065) if environment=='BUTTON_TRACK' else response['scatter']
    glare.inputs['Threshold'].default_value = 2.5 if environment=='BUTTON_TRACK' else response['threshold']
    glare.inputs['Strength'].default_value = scatter
    glare.inputs['Size'].default_value = .010 if environment=='BUTTON_TRACK' else .015
    glare.mute = not inspection or scatter<=0
    scene['pipe_camera_response_status'] = ('Subpixel optics and restrained highlight scatter'
                                             if enabled else 'Studio optical response bypassed')
    scene['pipe_camera_response_sigma_px'] = sigma if enabled else 0.0
    scene['pipe_camera_softness_px'] = extra * resolution / reference_width
    scene['pipe_camera_response_scatter'] = scatter if inspection else 0.0
    scene['pipe_camera_response_calibrated'] = False
    return True


def set_diagnostic_mode(scene, enabled):
    """Bypass all compositor effects for masks; restore prior state exactly."""
    if enabled:
        if not scene.get(DIAGNOSTIC, False):
            scene[RESTORE] = bool(scene.render.use_compositing)
            scene[DIAGNOSTIC] = True
        scene.render.use_compositing = False
    elif scene.get(DIAGNOSTIC, False):
        scene.render.use_compositing = bool(scene.get(RESTORE, True))
        del scene[DIAGNOSTIC]
        if RESTORE in scene:
            del scene[RESTORE]
