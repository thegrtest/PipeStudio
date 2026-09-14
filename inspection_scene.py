"""Procedural inspection fixtures for Pipe Studio's reference environments.

Geometry is deliberately separate from the pipe, camera and lights. All pieces
are real mesh objects, so their shadows, occlusion and reflections respond to
the scene. Dimensions describe an illustrative inspection rig in scene units;
they are not calibrated measurements of the photographed equipment.
"""

import math

import bpy


PREFIX = "PS_EnvMachine_"
GODS_PREFIX = "PS_EnvGods_"


def _name(name):
    if name.startswith('GodsLight'):
        return GODS_PREFIX + name[len('GodsLight'):]
    return PREFIX + name


def _material(name, color, metallic=0.8, roughness=0.5, grain=0.12):
    material = bpy.data.materials.get(_name(name))
    if material is None:
        material = bpy.data.materials.new(_name(name))
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = (620, 0)
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.location = (340, 0)
    shader.inputs['Base Color'].default_value = (*color, 1)
    shader.inputs['Metallic'].default_value = metallic
    shader.inputs['Roughness'].default_value = roughness
    if metallic < 0.3:
        shader.inputs['Specular IOR Level'].default_value = 0.16
    links.new(shader.outputs['BSDF'], out.inputs['Surface'])
    coords = nodes.new('ShaderNodeTexCoord')
    coords.location = (-750, 0)
    mapping = nodes.new('ShaderNodeVectorMath')
    mapping.operation = 'MULTIPLY'
    mapping.inputs[1].default_value = (1.5, 1.5, 20.0)
    mapping.location = (-560, 0)
    links.new(coords.outputs['Generated'], mapping.inputs[0])
    noise = nodes.new('ShaderNodeTexNoise')
    noise.location = (-370, 0)
    noise.inputs['Scale'].default_value = 95
    noise.inputs['Detail'].default_value = 2
    noise.inputs['Roughness'].default_value = 0.7
    links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
    ramp = nodes.new('ShaderNodeValToRGB')
    ramp.location = (-80, 90)
    ramp.color_ramp.elements[0].position = 0.12
    ramp.color_ramp.elements[0].color = (*[c * (1 - grain) for c in color], 1)
    ramp.color_ramp.elements[1].position = 0.88
    ramp.color_ramp.elements[1].color = (*[min(1, c * (1 + grain)) for c in color], 1)
    links.new(noise.outputs['Fac'], ramp.inputs['Fac'])
    links.new(ramp.outputs['Color'], shader.inputs['Base Color'])
    # Low-frequency handling marks modulate the finish independently of its
    # fine machining grain; avoid perfectly uniform steel and painted faces.
    handling = nodes.new('ShaderNodeTexNoise')
    handling.name = 'Uneven handling and cleaning'
    handling.inputs['Scale'].default_value = 4.2
    handling.inputs['Detail'].default_value = 3
    links.new(coords.outputs['Generated'], handling.inputs['Vector'])
    finish = nodes.new('ShaderNodeMapRange')
    finish.name = 'Uneven fixture roughness'
    finish.inputs['To Min'].default_value = max(.08, roughness - .09)
    finish.inputs['To Max'].default_value = min(.98, roughness + .10)
    links.new(handling.outputs['Fac'], finish.inputs['Value'])
    links.new(finish.outputs['Result'], shader.inputs['Roughness'])
    smudges = nodes.new('ShaderNodeMixRGB')
    smudges.name = 'Subtle worn finish'
    smudges.blend_type = 'MULTIPLY'
    smudges.inputs[0].default_value = .18
    links.new(ramp.outputs['Color'], smudges.inputs[1])
    links.new(handling.outputs['Fac'], smudges.inputs[2])
    links.new(smudges.outputs[0], shader.inputs['Base Color'])
    bump = nodes.new('ShaderNodeBump')
    bump.location = (100, -170)
    bump.inputs['Strength'].default_value = 0.12
    bump.inputs['Distance'].default_value = 0.002
    links.new(noise.outputs['Fac'], bump.inputs['Height'])
    links.new(bump.outputs['Normal'], shader.inputs['Normal'])
    return material


def _mesh(collection, name, vertices, faces, material, smooth=False):
    data = bpy.data.meshes.new(_name(name))
    data.from_pydata(vertices, [], faces)
    data.update()
    obj = bpy.data.objects.new(_name(name), data)
    collection.objects.link(obj)
    obj.data.materials.append(material)
    if smooth:
        for polygon in data.polygons:
            polygon.use_smooth = len(polygon.vertices) <= 4
    obj['pipe_studio_fixture'] = True
    return obj


def _bevel(obj, width):
    modifier = obj.modifiers.new('Machined edge radius', 'BEVEL')
    modifier.width = width
    modifier.segments = 3
    modifier.limit_method = 'ANGLE'
    modifier = obj.modifiers.new('Weighted surface normals', 'WEIGHTED_NORMAL')
    modifier.keep_sharp = True


def _box(collection, name, location, size, material, bevel=0.02):
    sx, sy, sz = [value * 0.5 for value in size]
    vertices = [(-sx, -sy, -sz), (sx, -sy, -sz), (sx, sy, -sz),
                (-sx, sy, -sz), (-sx, -sy, sz), (sx, -sy, sz),
                (sx, sy, sz), (-sx, sy, sz)]
    faces = [(0, 3, 2, 1), (4, 5, 6, 7), (0, 1, 5, 4),
             (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
    obj = _mesh(collection, name, vertices, faces, material)
    obj.location = location
    if bevel:
        _bevel(obj, bevel)
    return obj


def _cylinder(collection, name, location, radius, depth, material,
              axis='Z', bevel=0.015, vertices=96):
    points = [(radius * math.cos(i * math.tau / vertices),
               radius * math.sin(i * math.tau / vertices), z)
              for z in (-depth / 2, depth / 2) for i in range(vertices)]
    faces = [(i, (i + 1) % vertices, (i + 1) % vertices + vertices, i + vertices)
             for i in range(vertices)]
    faces += [tuple(reversed(range(vertices))), tuple(range(vertices, 2 * vertices))]
    obj = _mesh(collection, name, points, faces, material, smooth=True)
    obj.location = location
    if axis == 'Y':
        obj.rotation_euler.x = math.pi / 2
    elif axis == 'X':
        obj.rotation_euler.y = math.pi / 2
    if bevel:
        _bevel(obj, bevel)
    return obj


def _thread(collection, location, material, radius=0.292,
            length=1.9, pitch=0.14, crest_height=0.044):
    """One continuous triangular helical ridge with rounded crest and root."""
    steps = math.ceil(length / pitch * 56)
    # Cross-section in radius/height; blends into a separately modelled core.
    profile = ((0, -pitch * 0.42), (crest_height, -pitch * 0.075),
               (crest_height, pitch * 0.075), (0, pitch * 0.42))
    points = []
    for i in range(steps + 1):
        t = i / steps
        angle = t * length / pitch * math.tau
        for radial, axial in profile:
            points.append(((radius + radial) * math.cos(angle),
                           (radius + radial) * math.sin(angle),
                           -length / 2 + t * length + axial))
    faces = [(i * 4 + j, i * 4 + (j + 1) % 4,
              (i + 1) * 4 + (j + 1) % 4, (i + 1) * 4 + j)
             for i in range(steps) for j in range(4)]
    faces += [(3, 2, 1, 0), tuple(steps * 4 + j for j in range(4))]
    obj = _mesh(collection, 'LeadScrewThread', points, faces, material, smooth=True)
    obj.location = location
    return obj


def _clear(collection, prefix=PREFIX):
    # Restrict the operation to this module's own objects in the supplied rig.
    for obj in list(collection.objects):
        if obj.name.startswith(prefix):
            data = obj.data
            bpy.data.objects.remove(obj, do_unlink=True)
            if isinstance(data, bpy.types.Mesh) and data.users == 0:
                bpy.data.meshes.remove(data)


def build_machine(collection):
    """Upright reference rig, pipe centred at origin along Z, viewed from -Y.

    With a length-8 pipe the mouth is at Z=4 and the body extends below the
    intended close crop. Fixtures remain outside the central radius-0.9 pipe.
    Rebuilding the same collection replaces only objects owned by this module.
    """
    _clear(collection)
    dark = _material('DarkSteel', (0.009, 0.008, 0.006), 0.12, 0.92, 0.08)
    black = _material('BlackOxide', (0.003, 0.004, 0.0045), 0.10, 0.79, 0.12)
    steel = _material('CoolSteel', (0.06, 0.07, 0.08), 0.80, 0.65, 0.06)
    polished = _material('MachinedSteel', (0.48, 0.51, 0.52), 0.95, 0.24, 0.07)
    screw = _material('ThreadedSteel', (0.060, 0.073, 0.072), 0.68, 0.54, 0.08)
    objects = []
    add = objects.append
    add(_box(collection, 'RearPlate', (-1.3, 2.0, 2.0), (2.8, 0.23, 12), dark, 0.045))
    add(_box(collection, 'RearPlateEdge', (-2.69, 2.035, 2.0), (0.05, 0.29, 12), dark, 0.010))
    add(_box(collection, 'DistantBacking', (0.3, 5.5, 1.1), (14, 0.25, 13), black, 0))
    add(_cylinder(collection, 'WheelFace', (-5.5, 0.0, 1.0), 2.60, 0.60, black, 'Y', 0.06, 128))
    # Three shallow rim steps make the curved silhouette read as a real wheel.
    add(_cylinder(collection, 'WheelOuterRim', (-5.5, -0.10, 1.0), 2.64, 0.22, black, 'Y', 0.025, 128))
    add(_cylinder(collection, 'WheelInsetFace', (-5.5, -0.315, 1.0), 2.60, 0.04, black, 'Y', 0.012, 128))
    add(_box(collection, 'RearLeftFrame', (-3.6, 3.45, 1.0), (0.21, 0.35, 10), polished))
    add(_box(collection, 'RearTopCrossbar', (-3.7, 3.5, 3.98), (2.3, 0.28, 0.075), polished, 0.009))
    add(_box(collection, 'RearAngledBrace', (-3.68, 3.0, -0.6), (1.75, 0.35, 0.23), steel))
    objects[-1].rotation_euler.y = math.radians(19)
    add(_cylinder(collection, 'HangingCylinder', (1.90, 0.40, 4.40), 0.85, 5.30, steel, bevel=0.025))
    add(_cylinder(collection, 'CylinderBaseLip', (1.90, 0.40, 1.735), 0.847, 0.035, steel, bevel=0.007))
    add(_cylinder(collection, 'LeadScrewCore', (1.90, 0.40, 1.05), 0.292, 1.30, screw))
    add(_thread(collection, (1.90, 0.40, 1.05), screw, length=1.30, pitch=0.10, crest_height=0.037))
    add(_cylinder(collection, 'LowerShank', (1.90, 0.40, -0.15), 0.305, 1.10, polished, bevel=0.022))
    add(_cylinder(collection, 'ShankShoulder', (1.90, 0.40, 0.38), 0.317, 0.10, steel, bevel=0.009))
    add(_box(collection, 'RearMountingBracket', (2.10, 1.50, 0.50), (1.68, 0.68, 2.60), black, 0.045))
    add(_box(collection, 'BracketRightEdge', (2.90, 1.13, 0.50), (0.12, 0.07, 2.59), dark, 0.012))
    rail = _box(collection, 'BottomSilverRail', (0.50, -0.05, -1.95), (8.60, 0.74, 0.24), polished, 0.025)
    rail.rotation_euler.y = math.radians(-6.5)
    add(rail)
    add(_box(collection, 'BottomSupport', (0.7, 1.3, -2.52), (8.0, 1.65, 0.7), dark, 0.04))
    return objects


def _background_material(name, color=(0.4, 0.5, 0.3), gradient=False, soft_edge=False):
    """Broad lit surfaces that stay visible behind the strongly lit subject.

    A low-energy emissive component approximates distant diffusely illuminated
    machinery. The colors remain sub-unit and do not behave as clipped LEDs.
    Soft disk edges represent broad reflections rather than crisp painted dots.
    """
    material = bpy.data.materials.get(_name(name))
    if material is None:
        material = bpy.data.materials.new(_name(name))
    material.use_nodes = True
    nodes, links = material.node_tree.nodes, material.node_tree.links
    nodes.clear()
    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = (900, 0)
    coords = nodes.new('ShaderNodeTexCoord')
    coords.location = (-850, 0)
    shader = nodes.new('ShaderNodeBsdfPrincipled')
    shader.location = (430, 80)
    shader.inputs['Base Color'].default_value = (*[c * 0.035 for c in color], 1)
    shader.inputs['Roughness'].default_value = 1
    shader.inputs['Specular IOR Level'].default_value = 0
    shader.inputs['Emission Color'].default_value = (*color, 1)
    shader.inputs['Emission Strength'].default_value = 0.8
    links.new(shader.outputs['BSDF'], out.inputs['Surface'])
    if gradient:
        separate = nodes.new('ShaderNodeSeparateXYZ')
        separate.location = (-630, 120)
        links.new(coords.outputs['Generated'], separate.inputs[0])
        ramp = nodes.new('ShaderNodeValToRGB')
        ramp.location = (-430, 220)
        stops = ((0.0, (0.75, 0.82, 0.055)), (0.30, (0.70, 0.77, 0.14)),
                 (0.55, (0.38, 0.50, 0.29)), (1.0, (0.28, 0.45, 0.41)))
        ramp.color_ramp.elements.remove(ramp.color_ramp.elements[1])
        for index, (position, rgb) in enumerate(stops):
            element = ramp.color_ramp.elements[0] if index == 0 else ramp.color_ramp.elements.new(position)
            element.position = position
            element.color = (*rgb, 1)
        ramp.color_ramp.interpolation = 'EASE'
        links.new(separate.outputs['Z'], ramp.inputs['Fac'])
        mapping = nodes.new('ShaderNodeVectorMath')
        mapping.operation = 'MULTIPLY'
        mapping.inputs[1].default_value = (2.0, 0.05, 0.3)
        mapping.location = (-650, -180)
        links.new(coords.outputs['Generated'], mapping.inputs[0])
        noise = nodes.new('ShaderNodeTexNoise')
        noise.location = (-430, -180)
        noise.inputs['Scale'].default_value = 3
        noise.inputs['Detail'].default_value = 1
        links.new(mapping.outputs['Vector'], noise.inputs['Vector'])
        vary = nodes.new('ShaderNodeMixRGB')
        vary.blend_type = 'MULTIPLY'
        vary.inputs[0].default_value = 0.24
        vary.location = (140, 110)
        links.new(ramp.outputs['Color'], vary.inputs[1])
        links.new(noise.outputs['Fac'], vary.inputs[2])
        links.new(vary.outputs['Color'], shader.inputs['Emission Color'])
    if soft_edge:
        separate = nodes.new('ShaderNodeSeparateXYZ')
        separate.location = (-630, 0)
        links.new(coords.outputs['Generated'], separate.inputs[0])
        radial = nodes.new('ShaderNodeCombineXYZ')
        radial.location = (-430, 0)
        links.new(separate.outputs['X'], radial.inputs['X'])
        links.new(separate.outputs['Y'], radial.inputs['Y'])
        distance = nodes.new('ShaderNodeVectorMath')
        distance.operation = 'DISTANCE'
        distance.location = (-240, 0)
        distance.inputs[1].default_value = (0.5, 0.5, 0)
        links.new(radial.outputs[0], distance.inputs[0])
        alpha = nodes.new('ShaderNodeValToRGB')
        alpha.location = (-30, -100)
        alpha.color_ramp.elements[0].position = 0.18
        alpha.color_ramp.elements[0].color = (1, 1, 1, 1)
        alpha.color_ramp.elements[1].position = 0.50
        alpha.color_ramp.elements[1].color = (0, 0, 0, 1)
        alpha.color_ramp.interpolation = 'EASE'
        links.new(distance.outputs['Value'], alpha.inputs['Fac'])
        transparent = nodes.new('ShaderNodeBsdfTransparent')
        transparent.location = (420, -210)
        mix = nodes.new('ShaderNodeMixShader')
        mix.location = (700, 0)
        links.new(alpha.outputs['Color'], mix.inputs[0])
        links.new(transparent.outputs['BSDF'], mix.inputs[1])
        links.new(shader.outputs['BSDF'], mix.inputs[2])
        links.new(mix.outputs[0], out.inputs['Surface'])
    return material


def build_godslight(collection):
    """Horizontal +X pipe rig with a left mounting plate and distant green plant.

    The plate is just beyond the -X end of a length-8 model. Place the camera
    toward -Y and use depth of field to soften the spatial background machinery.
    No environment lighting is created here.
    """
    _clear(collection, GODS_PREFIX)
    silver = _material('GodsLightMount', (0.43, 0.46, 0.43), 0.87, 0.31, 0.08)
    wall = _background_material('GodsLightBroadGreen', gradient=True)
    shadow = _background_material('GodsLightShadowGreen', (0.14, 0.21, 0.12))
    cyan = _background_material('GodsLightPaleReflector', (0.65, 0.80, 0.68), soft_edge=True)
    yellow = _background_material('GodsLightLowerReflector', (0.95, 0.98, 0.085), soft_edge=True)
    warm = _background_material('GodsLightWarmReflector', (0.88, 0.52, 0.22), soft_edge=True)
    objects = []
    add = objects.append
    add(_box(collection, 'GodsLightMountPlate', (-4.24, 0.1, 0.0), (0.25, 3.7, 12.0), silver, 0.04))
    add(_cylinder(collection, 'GodsLightMandrelCollar', (-4.10, 0.0, 0.0), 0.98, 0.16, silver, 'X', 0.016))
    add(_box(collection, 'GodsLightBroadEnclosure', (1.0, 14.5, 0), (27, 0.45, 18), wall, 0.08))
    add(_box(collection, 'GodsLightRearPost', (-0.7, 12.2, 4.0), (1.45, 0.58, 8), shadow, 0.10))
    add(_cylinder(collection, 'GodsLightPaleDisk', (5.1, 11.5, 4.5), 3.0, 0.06, cyan, 'Y', 0))
    add(_cylinder(collection, 'GodsLightWarmDisk', (6.3, 10.5, 3.4), 2.9, 0.06, warm, 'Y', 0))
    add(_cylinder(collection, 'GodsLightYellowDisk', (5.0, 12.6, -4.0), 4.2, 0.06, yellow, 'Y', 0))
    return objects
