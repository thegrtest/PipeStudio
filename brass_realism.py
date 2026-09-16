"""Inspection-scale drawn brass: axial variation with sparse, fine oxidation.

These procedural fields use local geometry and respond to illumination. No
photographs, measured defects, or class-dependent textures enter this shader.
"""
def configure_drawn_finish(material, settings):
    def value(key, default):
        return settings.get(key,default) if isinstance(settings,dict) else getattr(settings,key,default)
    nodes=material.node_tree.nodes
    if value('product_mode','PIPE')!='PIPE':return
    scale=max(.05,value('radius',.9))/.9
    texture=value('texture_strength',.5)
    wear=value('wear',.35)
    for name in ('Alloy variation','Drawing undulation','Fine metal grain','Drawing lines','Scratch interruptions'):
        material.node_tree.links.new(nodes['Seeded finish coordinates'].outputs[0],nodes[name+'Scale'].inputs[0])
    # Fine flecks had covered most of the wall, giving it a cast/sandblasted
    # appearance. Drawn brass instead shows long faint tracks and isolated dirt.
    nodes['Sparse oxide grains'].inputs['From Min'].default_value=.58
    nodes['Sparse oxide grains'].inputs['From Max'].default_value=.79
    nodes['Oxide grain coverage'].inputs[1].default_value=.24
    nodes['Oxide island coverage'].inputs[1].default_value=.58
    # A continuous thin tarnish film replaces the old dense dark speckle field.
    # This softens reflections without suggesting hundreds of tiny defects.
    film=nodes.get('Thin oxide film')
    if film is None:
        film=nodes.new('ShaderNodeMath');film.name='Thin oxide film';film.operation='ADD'
        material.node_tree.links.new(nodes['Combined oxide coverage'].outputs[0],film.inputs[0])
        material.node_tree.links.new(film.outputs[0],nodes['Oxide control mask'].inputs[0])
    film.inputs[1].default_value=.40
    for name,stretch in (
        ('Fine oxide flecks',(115,150,150)),
        ('Oxide islands',(.45,4.5,4.5)),
        ('Fine metal grain',(125,175,175)),
        ('Drawing lines',(.46,140,140)),
        ('Drawing undulation',(1.15,20,20)),
        ('Long drawn waviness',(.18,7.5,7.5)),
        ('Burnished draw tracks',(.22,35,35))):
        nodes[name+'Scale'].inputs[1].default_value=tuple(v/scale for v in stretch)
    nodes['Grain roughness amplitude'].inputs[1].default_value=.025+texture*.055
    nodes['Drawing roughness amplitude'].inputs[1].default_value=.014+texture*.095
    nodes['DrawingBump'].inputs['Distance'].default_value=.0010*scale*(1+wear)
    nodes['DrawnWallBump'].inputs['Distance'].default_value=.0035*scale*(.25+wear)
    nodes['GrainBump'].inputs['Distance'].default_value=.00032*scale
    nodes['DrawingBump'].inputs['Strength'].default_value=texture*.35
    nodes['DrawnWallBump'].inputs['Strength'].default_value=texture*.40
    nodes['Scratch color amount'].inputs[1].default_value=.12+texture*.25
    nodes['Handling scuff color amount'].inputs[1].default_value=.29+texture*.12
    nodes['Handling smudge color amount'].inputs[1].default_value=.25+texture*.10
    nodes['BrassShader'].inputs['Anisotropic'].default_value=.25+texture*.20
    nodes['PolishedBrass'].inputs['Roughness'].default_value=max(.18,value('roughness',.45)*.68+.04)
    link=material.node_tree.links.new
    # Long, weak alloy/oxidation tracks occur in the metal reflectance itself,
    # including polished regions. They are not light streaks painted on top.
    stretch=nodes.get('Domain axial alloy coordinates')
    if stretch is None:
        stretch=nodes.new('ShaderNodeVectorMath');stretch.name='Domain axial alloy coordinates';stretch.operation='MULTIPLY'
        tex=nodes.new('ShaderNodeTexNoise');tex.name='Domain axial alloy tracks'
        tex.inputs['Scale'].default_value=1;tex.inputs['Detail'].default_value=2.2
        ramp=nodes.new('ShaderNodeValToRGB');ramp.name='Domain axial alloy color'
        ramp.color_ramp.elements[0].position=.22;ramp.color_ramp.elements[0].color=(.55,.58,.40,1)
        ramp.color_ramp.elements[1].position=.78;ramp.color_ramp.elements[1].color=(1.40,1.35,1.28,1)
        mix=nodes.new('ShaderNodeMixRGB');mix.name='Domain drawn alloy reflectance';mix.blend_type='MULTIPLY'
        link(stretch.outputs[0],tex.inputs['Vector']);link(tex.outputs['Fac'],ramp.inputs[0])
        link(ramp.outputs[0],mix.inputs[2])
    stretch.inputs[1].default_value=(.30/scale,36/scale,36/scale)
    link(nodes['Seeded finish coordinates'].outputs[0],stretch.inputs[0])
    mixed=nodes['Domain drawn alloy reflectance'];mixed.inputs[0].default_value=.55+wear*.50
    link(nodes['Handling scuff color'].outputs[0],mixed.inputs[1])
    for name in ('BrassShader','PolishedBrass'):link(mixed.outputs[0],nodes[name].inputs['Base Color'])
    configure_reference_microfinish(material, settings)


def configure_reference_microfinish(material, settings):
    """Resolve interrupted drawing and fine tarnish at inspection image scale.

    All variation is seeded in object space, not a screen-space photo overlay.
    The same finish is used for good, folded, dented and stained specimens.
    Reapplying settings replaces links/values instead of stacking shader layers.
    """
    def value(key, default):
        return settings.get(key,default) if isinstance(settings,dict) else getattr(settings,key,default)
    nodes=material.node_tree.nodes;link=material.node_tree.links.new
    scale=max(.05,value('radius',.9))/.9
    texture=max(0.,min(1.,value('texture_strength',.5)))
    wear=max(0.,min(1.,value('wear',.35)))
    oxide=max(0.,min(1.,value('oxide_amount',.4)))
    def node(kind,name):
        result=nodes.get(name)
        if result is None:result=nodes.new(kind);result.name=result.label=name
        return result
    def field(name,stretch,detail):
        coords=node('ShaderNodeVectorMath',name+' coordinates');coords.operation='MULTIPLY'
        coords.inputs[1].default_value=tuple(v/scale for v in stretch)
        link(nodes['Seeded finish coordinates'].outputs[0],coords.inputs[0])
        noise=node('ShaderNodeTexNoise',name);noise.inputs['Scale'].default_value=1
        noise.inputs['Detail'].default_value=detail;noise.inputs['Roughness'].default_value=.68
        link(coords.outputs[0],noise.inputs['Vector']);return noise
    def reflectance(name,noise,base,low,high,amount):
        ramp=node('ShaderNodeValToRGB',name+' range')
        ramp.color_ramp.elements[0].position=.24;ramp.color_ramp.elements[0].color=(*low,1)
        ramp.color_ramp.elements[1].position=.76;ramp.color_ramp.elements[1].color=(*high,1)
        link(noise.outputs['Fac'],ramp.inputs[0])
        mixed=node('ShaderNodeMixRGB',name);mixed.blend_type='MULTIPLY'
        mixed.inputs[0].default_value=amount
        link(base,mixed.inputs[1]);link(ramp.outputs[0],mixed.inputs[2])
        return mixed.outputs[0]

    # Previously an axial reflectance multiplier reached 0.9 with a 0.55–1.4
    # ramp, making high-contrast stripes that ran the entire pipe length.
    ramp=nodes['Domain axial alloy color'].color_ramp
    ramp.elements[0].color=(.65,.69,.59,1)
    ramp.elements[1].color=(1.24,1.21,1.16,1)
    nodes['Domain axial alloy coordinates'].inputs[1].default_value=(.65/scale,10/scale,10/scale)
    nodes['Domain drawn alloy reflectance'].inputs[0].default_value=.35+wear*.45
    for name,stretch in (('Fine metal grain',(50,68,68)),('Fine oxide flecks',(36,49,49)),
                         ('Oxide islands',(3.2,6,6)),('Drawing lines',(2.4,100,100)),
                         ('Long drawn waviness',(.75,9,9)),('Burnished draw tracks',(1.6,38,38))):
        nodes[name+'Scale'].inputs[1].default_value=tuple(v/scale for v in stretch)
    nodes['Scratch color amount'].inputs[1].default_value=.035+texture*.07
    nodes['Drawing roughness amplitude'].inputs[1].default_value=.01+texture*.035
    nodes['DrawnWallBump'].inputs['Distance'].default_value=.002*scale*(.25+wear)
    nodes['DrawnWallBump'].inputs['Strength'].default_value=texture*.28
    nodes['BrassShader'].inputs['Anisotropic'].default_value=.12+texture*.15
    nodes['PolishedBrass'].inputs['Anisotropic'].default_value=.18+texture*.17
    nodes['PolishedBrass'].inputs['Roughness'].default_value=max(.25,value('roughness',.45)*.76+.035)
    nodes['Sparse oxide grains'].inputs['From Min'].default_value=.42
    nodes['Sparse oxide grains'].inputs['From Max'].default_value=.70
    nodes['Oxide grain coverage'].inputs[1].default_value=.30
    nodes['Oxide island coverage'].inputs[1].default_value=.32
    nodes['Thin oxide film'].inputs[1].default_value=.28

    meso=field('Inspection uneven tarnish',(4.0,7.0,7.0),3.5)
    fine=field('Inspection resolved grain',(42,58,58),2.5)
    color=reflectance('Inspection mottled alloy',meso,nodes['Domain drawn alloy reflectance'].outputs[0],
                      (.64,.67,.58),(1.14,1.13,1.09),.14+oxide*.20)
    color=reflectance('Inspection grain reflectance',fine,color,
                      (.30,.34,.26),(1.36,1.32,1.23),.48+texture*.40)
    for name in ('BrassShader','PolishedBrass'):link(color,nodes[name].inputs['Base Color'])
    # The thin oxide also carries fine grain; otherwise it flattens all the
    # surface detail precisely on the more tarnished training specimens.
    oxide_color=reflectance('Inspection grain in tarnish',fine,nodes['OxideColors'].outputs[0],
                            (.56,.60,.49),(1.30,1.27,1.18),.30+oxide*.18)
    link(oxide_color,nodes['DullOxide'].inputs['Base Color'])
    # Small changes in roughness and normal alter reflected light instead of
    # merely painting a noisy colour on an otherwise perfect cylinder.
    rough=node('ShaderNodeMapRange','Inspection grain roughness')
    rough.clamp=True
    rough.inputs['From Min'].default_value=.25;rough.inputs['From Max'].default_value=.75
    rough.inputs['To Min'].default_value=.15;rough.inputs['To Max'].default_value=-.14
    link(fine.outputs['Fac'],rough.inputs['Value'])
    varying=node('ShaderNodeMath','Inspection varied roughness');varying.operation='ADD'
    link(nodes['Roughness maximum'].outputs[0],varying.inputs[0])
    link(rough.outputs[0],varying.inputs[1])
    link(varying.outputs[0],nodes['BrassShader'].inputs['Roughness'])
    nodes['GrainBump'].inputs['Distance'].default_value=.0009*scale

    # Infrequent, short bright handling traces. Voronoi cell-edge fragments
    # are gated by a separate field so there is no continuous web or stripe.
    scratches=node('ShaderNodeTexVoronoi','Inspection fragmented traces')
    scratches.feature='DISTANCE_TO_EDGE';scratches.inputs['Scale'].default_value=1
    link(nodes['Inspection resolved grain coordinates'].outputs[0],scratches.inputs['Vector'])
    trace=node('ShaderNodeMapRange','Inspection fine trace width');trace.clamp=True
    trace.inputs['From Min'].default_value=.006;trace.inputs['From Max'].default_value=.034
    trace.inputs['To Min'].default_value=1;trace.inputs['To Max'].default_value=0
    link(scratches.outputs['Distance'],trace.inputs['Value'])
    gate=node('ShaderNodeMapRange','Inspection trace interruptions');gate.clamp=True
    gate.inputs['From Min'].default_value=.57;gate.inputs['From Max'].default_value=.72
    link(meso.outputs['Fac'],gate.inputs['Value'])
    mask=node('ShaderNodeMath','Inspection sparse traces');mask.operation='MULTIPLY'
    link(trace.outputs[0],mask.inputs[0]);link(gate.outputs[0],mask.inputs[1])
    weight=node('ShaderNodeMath','Inspection trace amount');weight.operation='MULTIPLY'
    weight.inputs[1].default_value=.30+value('finish_marks',.3)*.4
    link(mask.outputs[0],weight.inputs[0])
    exposed=node('ShaderNodeMixRGB','Inspection exposed trace colour')
    exposed.inputs[2].default_value=(.95,.81,.41,1)
    link(weight.outputs[0],exposed.inputs[0]);link(color,exposed.inputs[1])
    for name in ('BrassShader','PolishedBrass'):link(exposed.outputs[0],nodes[name].inputs['Base Color'])
    material['domain_material_version']='inspection-microfinish-3'
    from brass_spectrum import configure_spectral_grain
    configure_spectral_grain(material,settings)
    from brass_microdetail import configure_local_details
    configure_local_details(material,settings)
