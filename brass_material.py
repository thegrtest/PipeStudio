"""Procedural drawn-brass surface for the hollow pipe inspection scenes.

No source photograph is baked onto the metal: the surface continues to respond
to new lights, camera angles and geometric defects. Coordinates and the brushing
tangent follow the pipe's local X axis when the object is rotated upright.
"""

import math
import random


def build_brass(material):
    """Build the shader once; update_brass changes its exposed control nodes."""
    material.use_nodes = True
    nodes = material.node_tree.nodes
    nodes.clear()
    link = material.node_tree.links.new

    def node(kind, name, x, y):
        item = nodes.new(kind)
        item.name = item.label = name
        item.location = (x, y)
        return item

    def math_node(name, operation, a, b, x, y):
        item = node('ShaderNodeMath', name, x, y)
        item.operation = operation
        for value, socket in ((a, item.inputs[0]), (b, item.inputs[1])):
            if hasattr(value, 'node'):
                link(value, socket)
            else:
                socket.default_value = value
        return item

    def noise(name, scale, detail, x, y, coordinates=None):
        stretch = node('ShaderNodeVectorMath', name+'Scale', x-190, y)
        stretch.operation = 'MULTIPLY'
        stretch.inputs[1].default_value = scale
        link(coordinates if coordinates is not None else coords.outputs['Object'], stretch.inputs[0])
        item = node('ShaderNodeTexNoise', name, x, y)
        item.inputs['Scale'].default_value = 1
        item.inputs['Detail'].default_value = detail
        item.inputs['Roughness'].default_value = .65
        link(stretch.outputs['Vector'], item.inputs['Vector'])
        return item

    coords = node('ShaderNodeTexCoord', 'Local material coordinates', -1600, 200)
    shader = node('ShaderNodeBsdfPrincipled', 'BrassShader', 1180, 300)
    shader.inputs['Metallic'].default_value = 1
    shader.inputs['Roughness'].default_value = .34
    output = node('ShaderNodeOutputMaterial', 'Brass output', 1500, 300)
    link(shader.outputs['BSDF'], output.inputs['Surface'])

    # Broad alloy variations stay very low contrast; intermediate length scales
    # carry the uneven highlights visible in the inspection photographs.
    patina = noise('Alloy variation', (1.7, 2.7, 2.7), 3, -1150, 750)
    meso = noise('Drawing undulation', (3.2, 22, 22), 2.4, -1150, 300)
    grain = noise('Fine metal grain', (125, 175, 175), 2, -1150, -350)
    lines = noise('Drawing lines', (.70, 195, 195), 2, -1150, -850)
    breaks = noise('Scratch interruptions', (5.5, 12, 12), 1.5, -1150, -1200)

    ramp = node('ShaderNodeValToRGB', 'AlloyColors', -600, 850)
    ramp.color_ramp.elements[0].position = .15
    ramp.color_ramp.elements[1].position = .85
    link(patina.outputs['Fac'], ramp.inputs['Fac'])

    # A smooth sparse mask produces shallow interrupted drawing scratches, not
    # regularly spaced stripes. Their modest brightening resembles worn metal.
    scratches = node('ShaderNodeMapRange', 'Sparse drawing scratches', -790, -850)
    scratches.clamp = True
    scratches.interpolation_type = 'SMOOTHSTEP'
    scratches.inputs['From Min'].default_value = .67
    scratches.inputs['From Max'].default_value = .80
    link(lines.outputs['Fac'], scratches.inputs['Value'])
    gate = node('ShaderNodeMapRange', 'Broken scratch mask', -790, -1160)
    gate.clamp = True
    gate.interpolation_type = 'SMOOTHSTEP'
    gate.inputs['From Min'].default_value = .35
    gate.inputs['From Max'].default_value = .65
    link(breaks.outputs['Fac'], gate.inputs['Value'])
    scratch_mask = math_node('Scratch mask', 'MULTIPLY', scratches.outputs[0], gate.outputs[0], -560, -900)
    scratch_color = math_node('Scratch color amount', 'MULTIPLY', scratch_mask.outputs[0], .12, -340, 620)
    color = node('ShaderNodeMixRGB', 'Fresh metal in drawing marks', -80, 850)
    color.blend_type = 'MIX'
    color.inputs[2].default_value = (.68, .52, .20, 1)
    link(scratch_color.outputs[0], color.inputs[0])
    link(ramp.outputs['Color'], color.inputs[1])
    link(color.outputs['Color'], shader.inputs['Base Color'])

    base = node('ShaderNodeValue', 'RoughnessBase', -560, 400)
    base.outputs[0].default_value = .34
    rough_patina = math_node('Centered alloy roughness', 'SUBTRACT', patina.outputs['Fac'], .5, -790, 620)
    rough_patina = math_node('Patina roughness amplitude', 'MULTIPLY', rough_patina.outputs[0], .07, -560, 620)
    rough_meso = math_node('Centered drawing roughness', 'SUBTRACT', meso.outputs['Fac'], .5, -790, 200)
    rough_meso = math_node('Drawing roughness amplitude', 'MULTIPLY', rough_meso.outputs[0], .050, -560, 200)
    rough_grain = math_node('Centered grain roughness', 'SUBTRACT', grain.outputs['Fac'], .5, -790, -250)
    rough_grain = math_node('Grain roughness amplitude', 'MULTIPLY', rough_grain.outputs[0], .075, -560, -250)
    scratch_roughness = math_node('Scratches lower roughness', 'MULTIPLY', scratch_mask.outputs[0], -.045, -330, -680)
    rough_sum = math_node('Alloy roughness', 'ADD', base.outputs[0], rough_patina.outputs[0], -320, 380)
    rough_sum = math_node('Drawing roughness', 'ADD', rough_sum.outputs[0], rough_meso.outputs[0], -100, 380)
    rough_sum = math_node('Grain roughness', 'ADD', rough_sum.outputs[0], rough_grain.outputs[0], 120, 380)
    rough_sum = math_node('Scratch roughness', 'ADD', rough_sum.outputs[0], scratch_roughness.outputs[0], 340, 380)
    rough_min = math_node('Roughness minimum', 'MAXIMUM', rough_sum.outputs[0], .045, 560, 380)
    rough_max = math_node('Roughness maximum', 'MINIMUM', rough_min.outputs[0], .94, 780, 380)
    link(rough_max.outputs[0], shader.inputs['Roughness'])

    # Optional unlabelled finish variation: handling smudges, tiny dark flecks
    # and broader axial scuffs. These change reflectance only, never the mesh,
    # displacement socket or the geometric defect-mask attribute.
    finish = node('ShaderNodeValue', 'Finish marks amount', -1750, -1500)
    finish.outputs[0].default_value = 0
    seeded = node('ShaderNodeVectorMath', 'Seeded finish coordinates', -1750, -1780)
    seeded.operation = 'ADD'
    link(coords.outputs['Object'], seeded.inputs[0])
    seeded.inputs[1].default_value = (0, 0, 0)
    smudge = noise('Handling smudges', (1.2, 2.0, 2.0), 2.2, -1340, -1550, seeded.outputs[0])
    specks = noise('Sparse dark pinpricks', (44, 58, 58), 1.5, -1340, -1900, seeded.outputs[0])
    scuffs = noise('Handling scuffs', (.36, 72, 72), 1.7, -1340, -2300, seeded.outputs[0])
    scuff_breaks = noise('Handling scuff breaks', (1.4, 4.0, 4.0), 2, -1340, -2640, seeded.outputs[0])

    def finish_mask(name, texture, low, high, x, y):
        mapped = node('ShaderNodeMapRange', name, x, y)
        mapped.clamp = True
        mapped.interpolation_type = 'SMOOTHSTEP'
        mapped.inputs['From Min'].default_value = low
        mapped.inputs['From Max'].default_value = high
        link(texture.outputs['Fac'], mapped.inputs['Value'])
        return mapped

    smudge_mask = finish_mask('Soft handling smudge mask', smudge, .43, .73, -1110, -1550)
    speck_mask = finish_mask('Rare irregular pinprick mask', specks, .72, .86, -1110, -1900)
    scuff_mask = finish_mask('Long handling scuff mask', scuffs, .64, .79, -1110, -2300)
    scuff_gate = finish_mask('Interrupted handling scuffs', scuff_breaks, .38, .65, -1110, -2640)
    scuff_mask = math_node('Coherent handling scuffs', 'MULTIPLY', scuff_mask.outputs[0],
                           scuff_gate.outputs[0], -880, -2350)
    finish_color = color.outputs['Color']
    finish_rough = rough_sum.outputs[0]
    for name, mask, tint, color_amount, rough_amount, y in (
            ('Handling smudge', smudge_mask.outputs[0], (.37, .26, .09, 1), .30, .10, -1500),
            ('Dark pinprick', speck_mask.outputs[0], (.08, .056, .020, 1), .58, .13, -1880),
            ('Handling scuff', scuff_mask.outputs[0], (.69, .49, .17, 1), .40, .045, -2260)):
        amount = math_node(name+' coverage', 'MULTIPLY', mask, finish.outputs[0], -650, y)
        tint_amount = math_node(name+' color amount', 'MULTIPLY', amount.outputs[0], color_amount, -440, y)
        mixed = node('ShaderNodeMixRGB', name+' color', -220, y)
        mixed.blend_type = 'MIX'
        mixed.inputs[2].default_value = tint
        link(tint_amount.outputs[0], mixed.inputs[0])
        link(finish_color, mixed.inputs[1])
        finish_color = mixed.outputs[0]
        rough_amount_node = math_node(name+' roughness amount', 'MULTIPLY', amount.outputs[0], rough_amount, 10, y)
        rough_added = math_node(name+' roughness', 'ADD', finish_rough, rough_amount_node.outputs[0], 240, y)
        finish_rough = rough_added.outputs[0]
    link(finish_color, shader.inputs['Base Color'])
    link(finish_rough, rough_min.inputs[0])

    # The broad shallow irregularities and tiny etched marks perturb the normals
    # independently. This avoids turning the brass into rough stone or foil.
    meso_bump = node('ShaderNodeBump', 'DrawingBump', -290, -100)
    meso_bump.inputs['Strength'].default_value = .2
    meso_bump.inputs['Distance'].default_value = .0012
    link(meso.outputs['Fac'], meso_bump.inputs['Height'])
    scratch_bump = node('ShaderNodeBump', 'ScratchBump', -40, -160)
    scratch_bump.invert = True
    scratch_bump.inputs['Strength'].default_value = .18
    scratch_bump.inputs['Distance'].default_value = .00015
    link(scratch_mask.outputs[0], scratch_bump.inputs['Height'])
    link(meso_bump.outputs['Normal'], scratch_bump.inputs['Normal'])
    grain_bump = node('ShaderNodeBump', 'GrainBump', 210, -160)
    grain_bump.inputs['Strength'].default_value = .14
    grain_bump.inputs['Distance'].default_value = .0006
    link(grain.outputs['Fac'], grain_bump.inputs['Height'])
    link(scratch_bump.outputs['Normal'], grain_bump.inputs['Normal'])
    link(grain_bump.outputs['Normal'], shader.inputs['Normal'])

    tangent = node('ShaderNodeVectorTransform', 'Axial brushing tangent', 760, -100)
    tangent.vector_type = 'VECTOR'
    tangent.convert_from = 'OBJECT'
    tangent.convert_to = 'WORLD'
    tangent.inputs['Vector'].default_value = (1, 0, 0)
    if 'Tangent' in shader.inputs:
        link(tangent.outputs['Vector'], shader.inputs['Tangent'])
    if 'Anisotropic' in shader.inputs:
        shader.inputs['Anisotropic'].default_value = .28
    material.diffuse_color = (.60, .43, .16, 1)
    _build_inspection_layers(material, coords, shader, output, grain_bump, tangent)
    material['pipe_brass_version'] = 4
    return material


def _build_inspection_layers(material, coords, substrate, output, grain_bump, tangent):
    """Interleaved exposed brass, dull oxide islands, and polished draw tracks.

    All fields use seeded local 3D coordinates. Nothing stores illumination in
    an albedo image, and no displacement is added to the diagnostic geometry.
    """
    nodes=material.node_tree.nodes; link=material.node_tree.links.new
    def node(kind,name):
        n=nodes.new(kind); n.name=n.label=name; return n
    def math_node(name,op,a,b):
        n=node('ShaderNodeMath',name); n.operation=op
        for value,socket in ((a,n.inputs[0]),(b,n.inputs[1])):
            if hasattr(value,'node'): link(value,socket)
            else: socket.default_value=value
        return n.outputs[0]
    def texture(name,scale,detail):
        n=node('ShaderNodeTexNoise',name); n.inputs['Scale'].default_value=1
        n.inputs['Detail'].default_value=detail; n.inputs['Roughness'].default_value=.68
        stretch=node('ShaderNodeVectorMath',name+'Scale'); stretch.operation='MULTIPLY'
        stretch.inputs[1].default_value=scale
        link(nodes['Seeded finish coordinates'].outputs[0],stretch.inputs[0]); link(stretch.outputs[0],n.inputs['Vector'])
        return n.outputs['Fac']
    def map_range(name,value,low,high):
        n=node('ShaderNodeMapRange',name); n.clamp=True; n.interpolation_type='SMOOTHSTEP'
        n.inputs['From Min'].default_value=low; n.inputs['From Max'].default_value=high
        link(value,n.inputs['Value']); return n.outputs[0]

    broad=texture('Oxide islands',(.75,3.2,3.2),3.2)
    flecks=texture('Fine oxide flecks',(48,65,65),2)
    waviness=texture('Long drawn waviness',(.50,5.0,5.0),2.2)
    tracks=texture('Burnished draw tracks',(.35,28,28),2.5)
    breaks=texture('Interrupted polished tracks',(2.5,4.0,4.0),2.5)
    islands=map_range('Irregular oxide islands',broad,.37,.68)
    fine=map_range('Sparse oxide grains',flecks,.43,.64)
    patina=math_node('Oxide island coverage','MULTIPLY',islands,.80)
    fine=math_node('Oxide grain coverage','MULTIPLY',fine,.60)
    oxide_mask=math_node('Combined oxide coverage','ADD',patina,fine)
    oxide=nodes.new('ShaderNodeValue'); oxide.name=oxide.label='OxideAmount'
    oxide_mask=math_node('Oxide control mask','MULTIPLY',oxide_mask,oxide.outputs[0])

    polished_mask=map_range('Irregular polished tracks',tracks,.32,.72)
    interruptions=map_range('Polished track breaks',breaks,.23,.75)
    polished_mask=math_node('Interrupted polish mask','MULTIPLY',polished_mask,interruptions)
    polish=nodes.new('ShaderNodeValue'); polish.name=polish.label='PolishAmount'
    polished_mask=math_node('Polished track weight','MULTIPLY',polished_mask,polish.outputs[0])
    polish_floor=math_node('Fine polished grain floor','MULTIPLY',polish.outputs[0],.14)
    polished_mask=math_node('Polished microfacet coverage','ADD',polished_mask,polish_floor)
    polished_mask=math_node('Bounded polished mixture','MINIMUM',polished_mask,1.0)

    # Slow, shallow normal changes interrupt straight studio-perfect bands.
    wave_bump=node('ShaderNodeBump','DrawnWallBump')
    link(waviness,wave_bump.inputs['Height'])
    link(wave_bump.outputs['Normal'],nodes['DrawingBump'].inputs['Normal'])

    polished=node('ShaderNodeBsdfPrincipled','PolishedBrass')
    polished.inputs['Metallic'].default_value=1
    link(grain_bump.outputs['Normal'],polished.inputs['Normal'])
    link(tangent.outputs[0],polished.inputs['Tangent'])
    link(nodes['Fresh metal in drawing marks'].outputs[0],polished.inputs['Base Color'])
    polished.inputs['Anisotropic'].default_value=.48
    mixed=node('ShaderNodeMixShader','Drawn and burnished brass')
    link(polished_mask,mixed.inputs[0]); link(substrate.outputs[0],mixed.inputs[1]); link(polished.outputs[0],mixed.inputs[2])

    oxide_shader=node('ShaderNodeBsdfPrincipled','DullOxide')
    oxide_shader.inputs['Metallic'].default_value=0
    oxide_shader.inputs['IOR'].default_value=1.48
    oxide_shader.inputs['Roughness'].default_value=.68
    oxide_color=node('ShaderNodeValToRGB','OxideColors')
    link(broad,oxide_color.inputs[0]); link(oxide_color.outputs[0],oxide_shader.inputs['Base Color'])
    link(grain_bump.outputs['Normal'],oxide_shader.inputs['Normal'])

    # Interior normals face the axis. Use that to give the bore a duller finish,
    # while annular cut faces get the brighter exposed-metal response.
    pos=node('ShaderNodeSeparateXYZ','Local pipe position'); link(coords.outputs['Object'],pos.inputs[0])
    radial=node('ShaderNodeCombineXYZ','Radial material position')
    link(pos.outputs['Y'],radial.inputs['Y']); link(pos.outputs['Z'],radial.inputs['Z'])
    geo=node('ShaderNodeNewGeometry','Geometric surface orientation')
    normal=node('ShaderNodeVectorTransform','Unperturbed local normal')
    normal.vector_type='NORMAL'; normal.convert_from='WORLD'; normal.convert_to='OBJECT'
    link(geo.outputs['Normal'],normal.inputs['Vector'])
    facing=node('ShaderNodeVectorMath','Wall facing axis'); facing.operation='DOT_PRODUCT'
    link(radial.outputs[0],facing.inputs[0]); link(normal.outputs[0],facing.inputs[1])
    inside=math_node('Bore surface','LESS_THAN',facing.outputs['Value'],0)
    inside=math_node('Interior oxide','MULTIPLY',inside,.18)
    oxide_mask=math_node('Interior and exterior finish','ADD',oxide_mask,inside)
    oxide_mask=math_node('Bounded oxide mixture','MINIMUM',oxide_mask,.88)
    patinated=node('ShaderNodeMixShader','Brass with oxide islands')
    link(oxide_mask,patinated.inputs[0]); link(mixed.outputs[0],patinated.inputs[1]); link(oxide_shader.outputs[0],patinated.inputs[2])
    normals=node('ShaderNodeSeparateXYZ','Cut edge normal'); link(normal.outputs[0],normals.inputs[0])
    axial=math_node('Axial edge normal','ABSOLUTE',normals.outputs['X'],0)
    edge=map_range('Exposed annular cut edge',axial,.55,.96)
    abs_x=math_node('Absolute axial position','ABSOLUTE',pos.outputs['X'],0)
    end=math_node('End rim location','GREATER_THAN',abs_x,3.99)
    edge=math_node('Exposed rim weight','MULTIPLY',edge,end)
    rim=node('ShaderNodeMixShader','Cut rim finish')
    link(edge,rim.inputs[0]); link(patinated.outputs[0],rim.inputs[1]); link(polished.outputs[0],rim.inputs[2])
    link(rim.outputs[0],output.inputs['Surface'])
    # Keep the new layers easy to find in the native shader editor.
    frame=nodes.new('NodeFrame'); frame.name=frame.label='V4 - exposed brass and patchy inspection finish'
    first=list(nodes).index(nodes['Oxide islands'])
    for index,n in enumerate(list(nodes)[first:]):
        if n!=frame:
            n.parent=frame; n.location=((index%7)*220,-(index//7)*220)


def update_brass(material, settings):
    """Apply the existing UI controls without rebuilding or loading textures."""
    if material.get('pipe_brass_version') != 4:
        build_brass(material)
    nodes = material.node_tree.nodes

    def setting(name, default):
        result = settings.get(name, default) if isinstance(settings, dict) else getattr(settings, name, default)
        return float(result) if isinstance(result, (int, float)) and math.isfinite(result) else default

    roughness = max(.04, min(.95, setting('roughness', .34)))
    texture = max(0, min(1, setting('texture_strength', .22)))
    wear = max(0, min(1, setting('wear', .18)))
    green = max(0, min(1, setting('brass_green', 0)))
    radius = max(.05, setting('radius', .9))
    material_scale = radius / .9
    shader = nodes['BrassShader']
    shader.inputs['Roughness'].default_value = roughness
    nodes['RoughnessBase'].outputs[0].default_value = roughness
    nodes['Patina roughness amplitude'].inputs[1].default_value = .035 + .14 * wear
    nodes['Drawing roughness amplitude'].inputs[1].default_value = .012 + texture * .10
    nodes['Grain roughness amplitude'].inputs[1].default_value = .025 + texture * .13
    nodes['Scratches lower roughness'].inputs[1].default_value = -(.015 + texture * .11)
    nodes['Scratch color amount'].inputs[1].default_value = texture * .35
    # Conductor color is scene-linear reflectance, not a diffuse yellow paint.
    # A generic brass reference starts at sRGB (.98,.90,.59), linearized here;
    # the olive control and patina remain visual adjustments, not alloy analysis.
    color = (.955 - .10 * green, .787 - .070 * green, .307 - .130 * green, 1)
    dark = .96 - wear * .22
    light = 1.025 - wear * .025
    ramp = nodes['AlloyColors'].color_ramp
    ramp.elements[0].color = tuple(c * dark for c in color[:3]) + (1,)
    ramp.elements[1].color = tuple(c * light for c in color[:3]) + (1,)
    nodes['Fresh metal in drawing marks'].inputs[2].default_value = tuple(min(1, c * 1.13) for c in color[:3]) + (1,)
    material.diffuse_color = color
    finish_marks = max(0, min(1, setting('finish_marks', 0)))
    nodes['Finish marks amount'].outputs[0].default_value = finish_marks
    # Stable local-coordinate offsets vary specimens while keeping a specimen's
    # exact finish fixed as its lights/camera/object rotation are changed.
    finish_rng = random.Random(int(setting('seed', 42)))
    nodes['Seeded finish coordinates'].inputs[1].default_value = tuple(finish_rng.uniform(-23, 23) for _ in range(3))
    for name, multiplier in (('Handling smudge color', .60), ('Dark pinprick color', .13),
                             ('Handling scuff color', 1.12)):
        nodes[name].inputs[2].default_value = tuple(min(1, c*multiplier) for c in color[:3]) + (1,)
    nodes['DrawingBump'].inputs['Strength'].default_value = texture * .62
    nodes['DrawingBump'].inputs['Distance'].default_value = .0012 * material_scale * (1+2.5*wear)
    nodes['ScratchBump'].inputs['Strength'].default_value = texture * .58
    nodes['ScratchBump'].inputs['Distance'].default_value = .00015 * material_scale
    nodes['GrainBump'].inputs['Strength'].default_value = texture * .55
    nodes['GrainBump'].inputs['Distance'].default_value = .0006 * material_scale
    if 'Anisotropic' in shader.inputs:
        shader.inputs['Anisotropic'].default_value = .20 + texture * .24
    # Keep the grain scale comparable when a thicker or thinner pipe is selected.
    for name, scale in (('Alloy variation', (1.7, 2.7, 2.7)),
                        ('Drawing undulation', (3.2, 22, 22)),
                        ('Fine metal grain', (125, 175, 175)),
                        ('Drawing lines', (.70, 195, 195)),
                        ('Scratch interruptions', (5.5, 12, 12)),
                        ('Handling smudges', (1.2, 2.0, 2.0)),
                        ('Sparse dark pinpricks', (44, 58, 58)),
                        ('Handling scuffs', (.36, 72, 72)),
                        ('Handling scuff breaks', (1.4, 4.0, 4.0))):
        nodes[name+'Scale'].inputs[1].default_value = tuple(c / material_scale for c in scale)

    # Inspection photographs resolve uneven axial machining at intermediate
    # scales. Keep that structure visible below final camera resolution instead
    # of averaging all marks into an overly smooth, uniform highlight.
    drawn=min(1.0,texture/.62)
    for name,original,target in (('Fine metal grain',(125,175,175),(32,48,48)),
                                 ('Drawing lines',(.70,195,195),(.70,45,45))):
        nodes[name+'Scale'].inputs[1].default_value=tuple((a+(b-a)*drawn)/material_scale for a,b in zip(original,target))
    nodes['DrawingBump'].inputs['Distance'].default_value*=1+4*drawn
    nodes['Grain roughness amplitude'].inputs[1].default_value*=1+1.1*drawn
    nodes['Patina roughness amplitude'].inputs[1].default_value*=1+.6*drawn
    nodes['Scratch color amount'].inputs[1].default_value*=1+.7*drawn
    nodes['Handling scuff color amount'].inputs[1].default_value=.40+.28*drawn
    nodes['Handling smudge color amount'].inputs[1].default_value=.30+.12*drawn
    low=nodes['AlloyColors'].color_ramp.elements[0]
    low.color=tuple(c*(1-.16*drawn) for c in low.color[:3])+(1,)
    oxide=max(0,min(1,setting('oxide_amount',.38)))
    polish=max(0,min(1,setting('polish_amount',.42)))
    nodes['OxideAmount'].outputs[0].default_value=oxide
    nodes['PolishAmount'].outputs[0].default_value=polish
    nodes['PolishedBrass'].inputs['Roughness'].default_value=max(.10,roughness*.48+.035)
    nodes['PolishedBrass'].inputs['Anisotropic'].default_value=.28+.34*drawn
    nodes['DrawnWallBump'].inputs['Strength'].default_value=.35*drawn
    nodes['DrawnWallBump'].inputs['Distance'].default_value=.008*material_scale*(.25+wear)
    nodes['DullOxide'].inputs['Roughness'].default_value=.60+.18*wear
    ramp=nodes['OxideColors'].color_ramp
    ramp.elements[0].color=(.060,.038+.015*green,.011,1)
    ramp.elements[1].color=(.22,.155+.025*green,.055,1)
    nodes['End rim location'].inputs[1].default_value=setting('length',6)/2-radius*setting('wall_ratio',.1)*1.2
    for name,scale in (('Oxide islands',(.75,3.2,3.2)),('Fine oxide flecks',(48,65,65)),
        ('Long drawn waviness',(.50,5,5)),('Burnished draw tracks',(.35,28,28)),('Interrupted polished tracks',(2.5,4,4))):
        nodes[name+'Scale'].inputs[1].default_value=tuple(c/material_scale for c in scale)

