"""Pipe Studio V4 brass adapted to the flashlight axis, plus seeded polymer finish."""
import random
from pathlib import Path
import bpy
from brass_material import build_brass,update_brass
from shell_appearance import POLYMER_DEFAULTS


def surface_dust(mat,p,seed):
    """Sparse finish layer, replaced with the rest of the material in label passes."""
    amount=p.get('dust_amount',.22)
    mat['inspection_dust_amount']=amount
    if amount<=0:return
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    coords=nodes.new('ShaderNodeTexCoord');coords.name='Dust attached to specimen'
    shifted=nodes.new('ShaderNodeVectorMath');shifted.operation='ADD'
    rng=random.Random(seed+7341)
    shifted.inputs[1].default_value=tuple(rng.uniform(-30,30) for _ in range(3))
    links.new(coords.outputs['Object'],shifted.inputs[0])
    def math_node(name,operation,a,b):
        node=nodes.new('ShaderNodeMath');node.name=name;node.operation=operation
        if isinstance(a,(int,float)):node.inputs[0].default_value=a
        else:links.new(a,node.inputs[0])
        if isinstance(b,(int,float)):node.inputs[1].default_value=b
        else:links.new(b,node.inputs[1])
        return node.outputs[0]
    def particles(name,scale,threshold):
        stretch=nodes.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY';stretch.inputs[1].default_value=scale
        links.new(shifted.outputs[0],stretch.inputs[0])
        cells=nodes.new('ShaderNodeTexVoronoi');cells.name=name;cells.inputs['Scale'].default_value=1
        links.new(stretch.outputs[0],cells.inputs['Vector'])
        shape=nodes.new('ShaderNodeMapRange');shape.clamp=True
        shape.inputs['From Min'].default_value=.035;shape.inputs['From Max'].default_value=threshold
        shape.inputs['To Min'].default_value=1;shape.inputs['To Max'].default_value=0
        links.new(cells.outputs['Distance'],shape.inputs['Value'])
        return shape.outputs[0]
    fine=particles('Fine dust grains',(36,36,36),.14)
    fibers=particles('Occasional tiny fibers',(24,5,24),.12)
    patch=nodes.new('ShaderNodeTexNoise');patch.name='Sparse deposition patches';patch.inputs['Scale'].default_value=7
    links.new(shifted.outputs[0],patch.inputs['Vector'])
    fine=math_node('Sparse fine dust','MULTIPLY',fine,math_node('Dust patch threshold','GREATER_THAN',patch.outputs['Fac'],.52))
    fibers=math_node('Sparse fiber selection','MULTIPLY',fibers,math_node('Fiber patch threshold','GREATER_THAN',patch.outputs['Fac'],.64))
    combined=math_node('Dust and fibers','ADD',fine,fibers)
    coverage=math_node('Dust amount control','MULTIPLY',combined,amount*3)
    coverage=math_node('Bounded dust coverage','MINIMUM',coverage,.9)
    dust=nodes.new('ShaderNodeBsdfPrincipled');dust.name='Matte normal dust and debris'
    dust.inputs['Base Color'].default_value=(.42,.36,.25,1)
    dust.inputs['Roughness'].default_value=.82;dust.inputs['Specular IOR Level'].default_value=.22
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.25;bump.inputs['Distance'].default_value=.0004
    links.new(combined,bump.inputs['Height']);links.new(bump.outputs[0],dust.inputs['Normal'])
    output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output)
    original=output.inputs['Surface'].links[0].from_socket
    mix=nodes.new('ShaderNodeMixShader');mix.name='Normal surface dust — excluded from defect labels'
    links.new(coverage,mix.inputs[0]);links.new(original,mix.inputs[1]);links.new(dust.outputs[0],mix.inputs[2])
    links.new(mix.outputs[0],output.inputs['Surface'])


def swap_xy(nodes,links,socket,name):
    targets=[link.to_socket for link in socket.links]
    split=nodes.new('ShaderNodeSeparateXYZ');split.name=name+' split'
    combine=nodes.new('ShaderNodeCombineXYZ');combine.name=name
    links.new(socket,split.inputs[0])
    links.new(split.outputs['Y'],combine.inputs['X'])
    links.new(split.outputs['X'],combine.inputs['Y'])
    links.new(split.outputs['Z'],combine.inputs['Z'])
    for target in targets:links.new(combine.outputs[0],target)


def track_finish(mat,rail=False):
    """Quiet directional wear on the conveyor; never a defect surface."""
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    shader=nodes.get('Principled BSDF')
    shader.inputs['Metallic'].default_value=.55 if rail else 0
    if rail:shader.inputs['Base Color'].default_value=(.028,.026,.015,1)
    coords=nodes.new('ShaderNodeTexCoord')
    stretch=nodes.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY';stretch.inputs[1].default_value=(2,120,30)
    links.new(coords.outputs['Object'],stretch.inputs[0])
    grain=nodes.new('ShaderNodeTexNoise');grain.name='Fine track contact wear';grain.inputs['Scale'].default_value=1;grain.inputs['Detail'].default_value=2
    links.new(stretch.outputs[0],grain.inputs['Vector'])
    rough=nodes.new('ShaderNodeMapRange');rough.inputs['To Min'].default_value=.24 if rail else .17
    rough.inputs['To Max'].default_value=.38 if rail else .26
    links.new(grain.outputs['Fac'],rough.inputs['Value']);links.new(rough.outputs[0],shader.inputs['Roughness'])
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.2;bump.inputs['Distance'].default_value=.0007
    links.new(grain.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs[0],shader.inputs['Normal'])


def brass(p,seed,face=False):
    mat=bpy.data.materials.new(f'Inspection V4 brass {seed} '+('face' if face else 'collar'))
    build_brass(mat)
    finish_rng=random.Random(seed+183)
    update_brass(mat,{**p,'radius':.5,'length':2.85,'seed':seed,
        'oxide_amount':min(1,p['oxide_amount']*finish_rng.uniform(.85,1.15)),
        'polish_amount':min(1,p['polish_amount']*finish_rng.uniform(.75,1.05))})
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    swap_xy(nodes,links,nodes['Local material coordinates'].outputs['Object'],'Flashlight Y-axis coordinates')
    swap_xy(nodes,links,nodes['Unperturbed local normal'].outputs[0],'Flashlight Y-axis normals')
    nodes['Axial brushing tangent'].inputs[0].default_value=(1,0,0) if face else (0,1,0)
    nodes['Grain roughness amplitude'].inputs[1].default_value*=1.2
    if face:
        # A closed face is not the freshly cut annulus of an open pipe.
        rim=nodes['Exposed rim weight'].inputs[1]
        for link in list(rim.links):links.remove(link)
        rim.default_value=0
        for node in nodes:
            if node.type=='BSDF_PRINCIPLED' and 'Anisotropic' in node.inputs:
                node.inputs['Anisotropic'].default_value=.08
        # The same packed height artwork drives slightly rougher stamp troughs.
        coords=nodes.new('ShaderNodeTexCoord');xyz=nodes.new('ShaderNodeSeparateXYZ')
        links.new(coords.outputs['Object'],xyz.inputs[0])
        uv=nodes.new('ShaderNodeCombineXYZ')
        for source,dest in [('X','X'),('Z','Y')]:
            add=nodes.new('ShaderNodeMath');add.operation='ADD';add.inputs[1].default_value=.5
            links.new(xyz.outputs[source],add.inputs[0]);links.new(add.outputs[0],uv.inputs[dest])
        artwork=bpy.data.images.load(str(Path(__file__).parent/'flashlight_lab/assets/cap_stamp_v2.png'),check_existing=True)
        artwork.colorspace_settings.name='Non-Color'
        if not artwork.packed_file:artwork.pack()
        stamp=nodes.new('ShaderNodeTexImage');stamp.name='Pressed lettering finish';stamp.image=artwork;stamp.extension='CLIP'
        links.new(uv.outputs[0],stamp.inputs['Vector'])
        weight=nodes.new('ShaderNodeMath');weight.operation='MULTIPLY';weight.inputs[1].default_value=.55
        links.new(stamp.outputs['Color'],weight.inputs[0])
        trough=nodes.new('ShaderNodeBsdfPrincipled');trough.name='Subtle oxidation inside impressed letters'
        trough.inputs['Base Color'].default_value=(.32,.245,.07,1);trough.inputs['Metallic'].default_value=1
        trough.inputs['Roughness'].default_value=min(.6,p['roughness']+.15)
        output=next(n for n in nodes if n.type=='OUTPUT_MATERIAL' and n.is_active_output)
        original=output.inputs['Surface'].links[0].from_socket
        stamped=nodes.new('ShaderNodeMixShader');stamped.name='Impressed lettering is normal brass finish'
        links.new(weight.outputs[0],stamped.inputs[0]);links.new(original,stamped.inputs[1]);links.new(trough.outputs[0],stamped.inputs[2])
        links.new(stamped.outputs[0],output.inputs['Surface'])
    surface_dust(mat,p,seed)
    return mat


def button(p,seed):
    """Pale polished alloy with fine forming grain, distinct from the brass seat."""
    mat=bpy.data.materials.new(f'Inspection center button alloy {seed}')
    mat.use_nodes=True
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    shader=nodes.get('Principled BSDF');shader.name='Button alloy'
    shader.inputs['Metallic'].default_value=1
    shader.inputs['Anisotropic'].default_value=.12
    coords=nodes.new('ShaderNodeTexCoord')
    offset=nodes.new('ShaderNodeVectorMath');offset.operation='ADD'
    rng=random.Random(seed+927)
    offset.inputs[1].default_value=tuple(rng.uniform(-10,10) for _ in range(3))
    links.new(coords.outputs['Object'],offset.inputs[0])
    grain=nodes.new('ShaderNodeTexNoise');grain.name='Fine pressed alloy grain'
    grain.inputs['Scale'].default_value=380;grain.inputs['Detail'].default_value=2
    links.new(offset.outputs[0],grain.inputs['Vector'])
    broad=nodes.new('ShaderNodeTexNoise');broad.name='Quiet alloy finish variation'
    broad.inputs['Scale'].default_value=28;broad.inputs['Detail'].default_value=2
    links.new(offset.outputs[0],broad.inputs['Vector'])
    color=nodes.new('ShaderNodeValToRGB');color.name='Pale warm button metal'
    color.color_ramp.elements[0].color=(.60,.56,.36,1)
    color.color_ramp.elements[1].color=(.82,.79,.62,1)
    links.new(broad.outputs['Fac'],color.inputs[0]);links.new(color.outputs[0],shader.inputs['Base Color'])
    rough=nodes.new('ShaderNodeMapRange');rough.name='Button polishing roughness'
    base=max(.18,min(.48,p['roughness']*.95))
    rough.inputs['To Min'].default_value=base*.85
    rough.inputs['To Max'].default_value=base*1.2
    links.new(grain.outputs['Fac'],rough.inputs['Value']);links.new(rough.outputs[0],shader.inputs['Roughness'])
    split=nodes.new('ShaderNodeSeparateXYZ');links.new(coords.outputs['Object'],split.inputs[0])
    planar=nodes.new('ShaderNodeCombineXYZ')
    links.new(split.outputs['X'],planar.inputs['X']);links.new(split.outputs['Z'],planar.inputs['Z'])
    radius=nodes.new('ShaderNodeVectorMath');radius.operation='LENGTH';links.new(planar.outputs[0],radius.inputs[0])
    scale=nodes.new('ShaderNodeMath');scale.operation='MULTIPLY';scale.inputs[1].default_value=1400
    links.new(radius.outputs['Value'],scale.inputs[0])
    rings=nodes.new('ShaderNodeMath');rings.name='Fine concentric forming lines';rings.operation='SINE'
    links.new(scale.outputs[0],rings.inputs[0])
    height=nodes.new('ShaderNodeMath');height.operation='MULTIPLY_ADD';height.inputs[1].default_value=.15
    links.new(rings.outputs[0],height.inputs[0]);links.new(grain.outputs['Fac'],height.inputs[2])
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.18;bump.inputs['Distance'].default_value=.00012
    links.new(height.outputs[0],bump.inputs['Height']);links.new(bump.outputs[0],shader.inputs['Normal'])
    mat['inspection_button_version']=2
    surface_dust(mat,{**p,'dust_amount':p.get('dust_amount',.22)*.65},seed)
    return mat


def groove_finish(mat,coords,normal,roughness,color,p,rib_spec):
    """Rib-aligned micro relief and sparse residue; beauty only, no new meshes."""
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    def op(name,operation,a,b=0):
        node=nodes.new('ShaderNodeMath');node.name=name;node.operation=operation
        for value,socket in ((a,node.inputs[0]),(b,node.inputs[1])):
            if isinstance(value,(int,float)):socket.default_value=value
            else:links.new(value,socket)
        return node.outputs[0]
    xyz=nodes.new('ShaderNodeSeparateXYZ');links.new(coords,xyz.inputs[0])
    theta=op('Groove polar angle','ARCTAN2',xyz.outputs['Z'],xyz.outputs['X'])
    phase=op('Actual extrusion rib count','MULTIPLY',theta,rib_spec['rib_count'])
    phase=op('Actual extrusion rib phase','ADD',phase,rib_spec['rib_phase'])
    drift=op('Axial groove drift','SINE',op('Axial drift scale','MULTIPLY',xyz.outputs['Y'],4))
    phase=op('Ribs follow the tube','ADD',phase,op('Subtle groove drift','MULTIPLY',drift,.06))
    crest=op('Rib crest profile','COSINE',phase)
    second=op('Defined rib shoulders','COSINE',op('Second groove harmonic','MULTIPLY',phase,2))
    height=op('Crisp groove relief','ADD',crest,op('Shoulder relief','MULTIPLY',second,.22))
    stretch_amp=nodes.new('ShaderNodeVectorMath');stretch_amp.operation='MULTIPLY';stretch_amp.inputs[1].default_value=(145,5,145)
    links.new(coords,stretch_amp.inputs[0])
    amplitude=nodes.new('ShaderNodeTexNoise');amplitude.name='Interrupted rib tooling polish';amplitude.noise_dimensions='4D'
    amplitude.inputs['Scale'].default_value=1;amplitude.inputs['Detail'].default_value=2.5
    amplitude.inputs['W'].default_value=(rib_spec['material_seed']%1009)*.13
    links.new(stretch_amp.outputs[0],amplitude.inputs['Vector'])
    local=nodes.new('ShaderNodeMapRange');local.clamp=True
    local.inputs['From Min'].default_value=.25;local.inputs['From Max'].default_value=.75
    finish_variation=p.get('plastic_finish_variation',POLYMER_DEFAULTS['plastic_finish_variation'])
    local.inputs['To Min'].default_value=.8-.65*finish_variation
    local.inputs['To Max'].default_value=.8+.6*finish_variation
    links.new(amplitude.outputs['Fac'],local.inputs['Value'])
    relief=op('Variable rib shoulder relief','MULTIPLY',height,local.outputs[0])
    bump=nodes.new('ShaderNodeBump');bump.name='Fine groove shoulder normals'
    bump.inputs['Strength'].default_value=min(1,p['texture_strength']*1.3)
    bump.inputs['Distance'].default_value=.0007*p.get('groove_definition',1.)
    links.new(relief,bump.inputs['Height']);links.new(normal,bump.inputs['Normal'])
    ridge=op('Polished ridge weight','MULTIPLY',op('Positive rib crests','ADD',crest,1),.5)
    polish=op('Interrupted crest polish','MULTIPLY',ridge,amplitude.outputs['Fac'])
    rough=op('Individual rib polishing','SUBTRACT',roughness,op('Ridge polish depth','MULTIPLY',polish,.095*p.get('groove_polish',.25)))
    rough=op('Bounded rib roughness','MAXIMUM',rough,.12)
    valley=op('Fine residue channel','POWER',op('Groove valley weight','SUBTRACT',1,ridge),14)
    stretch=nodes.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY';stretch.inputs[1].default_value=(23,4.5,23)
    links.new(coords,stretch.inputs[0])
    noise=nodes.new('ShaderNodeTexNoise');noise.name='Interrupted normal groove residue';noise.inputs['Scale'].default_value=1
    noise.inputs['Detail'].default_value=2;links.new(stretch.outputs[0],noise.inputs['Vector'])
    patches=nodes.new('ShaderNodeMapRange');patches.clamp=True
    patches.inputs['From Min'].default_value=.53;patches.inputs['From Max'].default_value=.72
    patches.inputs['To Max'].default_value=.20*p.get('groove_residue',.55)
    links.new(noise.outputs['Fac'],patches.inputs['Value'])
    residue=op('Sparse pale channel residue','MULTIPLY',valley,patches.outputs[0])
    mix=nodes.new('ShaderNodeMixRGB');mix.name='Normal groove residue — excluded from labels'
    links.new(residue,mix.inputs[0]);links.new(color,mix.inputs[1]);mix.inputs[2].default_value=(.32,.28,.21,1)
    mat['inspection_groove_count']=rib_spec['rib_count'];mat['inspection_groove_phase']=rib_spec['rib_phase']
    mat['inspection_finish_version']=5
    return bump.outputs[0],rough,mix.outputs[0]


def plastic(p,seed,body=False,rib_spec=None):
    rng=random.Random(seed)
    mat=bpy.data.materials.new(f'Inspection burgundy plastic polymer {seed}')
    mat.use_nodes=True
    nodes,links=mat.node_tree.nodes,mat.node_tree.links
    shader=nodes.get('Principled BSDF')
    controlled=p.get('environment')=='BUTTON_TRACK'
    shader.inputs['IOR'].default_value=1.46
    shader.inputs['Specular IOR Level'].default_value=p.get('plastic_specular',POLYMER_DEFAULTS['plastic_specular']) if controlled else .45
    shader.inputs['Coat Weight'].default_value=p.get('plastic_coat',POLYMER_DEFAULTS['plastic_coat']) if controlled else .10
    shader.inputs['Coat Roughness'].default_value=.35 if controlled else .32
    coords=nodes.new('ShaderNodeTexCoord')
    offset=nodes.new('ShaderNodeVectorMath');offset.operation='ADD'
    offset.inputs[1].default_value=tuple(rng.uniform(-20,20) for _ in range(3))
    links.new(coords.outputs['Object'],offset.inputs[0])
    def noise(name,scale,detail=2):
        stretch=nodes.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY';stretch.inputs[1].default_value=scale
        links.new(offset.outputs[0],stretch.inputs[0])
        tex=nodes.new('ShaderNodeTexNoise');tex.name=name;tex.inputs['Scale'].default_value=1;tex.inputs['Detail'].default_value=detail
        links.new(stretch.outputs[0],tex.inputs['Vector']);return tex
    broad=noise('Subtle pigment and handling variation',(3,2,3),3)
    grain=noise('Interrupted axial extrusion lines',(170,1.1,170),2.5)
    scuff=noise('Handling scuffs',(42,2.8,42),2)
    flecks=noise('Sparse pigment inclusions',(135,90,135),1.5)
    base=(.085*rng.uniform(.85,1.15),.009*rng.uniform(.8,1.2),.0058*rng.uniform(.9,1.1))
    ramp=nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color=(*(v*.75 for v in base),1)
    ramp.color_ramp.elements[1].color=(*(v*1.2 for v in base),1)
    links.new(broad.outputs['Fac'],ramp.inputs[0])
    scuffs=nodes.new('ShaderNodeMapRange');scuffs.clamp=True;scuffs.interpolation_type='SMOOTHSTEP'
    scuffs.inputs['From Min'].default_value=.64;scuffs.inputs['From Max'].default_value=.83
    scuffs.inputs['To Max'].default_value=p['finish_marks']*.65
    links.new(scuff.outputs['Fac'],scuffs.inputs['Value'])
    mix=nodes.new('ShaderNodeMixRGB');links.new(scuffs.outputs[0],mix.inputs[0]);links.new(ramp.outputs[0],mix.inputs[1])
    mix.inputs[2].default_value=(.24,.13,.08,1)
    specks=nodes.new('ShaderNodeMath');specks.operation='GREATER_THAN';specks.inputs[1].default_value=.78
    links.new(flecks.outputs['Fac'],specks.inputs[0])
    speck_mix=nodes.new('ShaderNodeMixRGB');links.new(specks.outputs[0],speck_mix.inputs[0]);links.new(mix.outputs[0],speck_mix.inputs[1])
    speck_mix.inputs[2].default_value=(.045,.027,.013,1);links.new(speck_mix.outputs[0],shader.inputs['Base Color'])
    rough=nodes.new('ShaderNodeMapRange');rough.name='Polymer base roughness'
    finish_amount=p.get('plastic_finish_variation',POLYMER_DEFAULTS['plastic_finish_variation']) if controlled else 1.
    rough_key='plastic_roughness' if body else 'crimp_roughness'
    base_rough=p.get(rough_key,POLYMER_DEFAULTS[rough_key])
    rough.inputs['To Min'].default_value=max(.12,base_rough-.045*finish_amount) if controlled else max(.10,p['roughness']-.11)
    rough.inputs['To Max'].default_value=min(.8,base_rough+.07*finish_amount) if controlled else min(.7,p['roughness']+.05+p['wear']*.08)
    links.new(scuff.outputs['Fac'],rough.inputs['Value'])
    rough_socket=rough.outputs[0]
    if controlled:
        # Mid-scale variation breaks up lamp reflections without denting geometry.
        handling=noise('Dull handled polymer patches',(8,3.5,8),2.5)
        patch=nodes.new('ShaderNodeMapRange');patch.name='Normal polymer roughness variation';patch.clamp=True
        patch.inputs['From Min'].default_value=.25;patch.inputs['From Max'].default_value=.75
        patch.inputs['To Min'].default_value=-.055*finish_amount
        patch.inputs['To Max'].default_value=.13*finish_amount
        links.new(handling.outputs['Fac'],patch.inputs['Value'])
        uneven=nodes.new('ShaderNodeMath');uneven.operation='ADD';uneven.name='Polymer with local dull patches'
        links.new(rough_socket,uneven.inputs[0]);links.new(patch.outputs[0],uneven.inputs[1])
        bounded=nodes.new('ShaderNodeClamp');bounded.inputs['Min'].default_value=.12;bounded.inputs['Max'].default_value=.8
        links.new(uneven.outputs[0],bounded.inputs['Value']);rough_socket=bounded.outputs[0]
        mat['inspection_finish_version']=5
        for key in ('plastic_roughness','plastic_specular','plastic_coat','plastic_finish_variation','groove_polish','groove_residue','crimp_roughness','plastic_ink_wear'):
            mat[key]=p.get(key,POLYMER_DEFAULTS[key])
    links.new(rough_socket,shader.inputs['Roughness'])
    bump=nodes.new('ShaderNodeBump');bump.inputs['Strength'].default_value=p['texture_strength']*.6
    bump.inputs['Distance'].default_value=.0014
    links.new(grain.outputs['Fac'],bump.inputs['Height']);links.new(bump.outputs[0],shader.inputs['Normal'])
    if body:
        # Fine extrusion wear varies the highlight across neighboring ribs.
        variation=nodes.new('ShaderNodeMath');variation.operation='MULTIPLY_ADD'
        variation.name='Fine axial polish variation';variation.inputs[1].default_value=.09*finish_amount;variation.inputs[2].default_value=-.045*finish_amount
        links.new(grain.outputs['Fac'],variation.inputs[0])
        rough_grain=nodes.new('ShaderNodeMath');rough_grain.operation='ADD';rough_grain.name='Broken extrusion reflections'
        links.new(rough_socket,rough_grain.inputs[0]);links.new(variation.outputs[0],rough_grain.inputs[1])
        bump.inputs['Distance'].default_value=.0022
        shader.inputs['Anisotropic'].default_value=.22
        tangent=nodes.new('ShaderNodeVectorTransform');tangent.vector_type='VECTOR';tangent.convert_from='OBJECT';tangent.convert_to='WORLD'
        tangent.inputs['Vector'].default_value=(0,1,0);links.new(tangent.outputs[0],shader.inputs['Tangent'])
        chips=noise('Sparse light handling flecks',(42,34,42),2)
        chip_mask=nodes.new('ShaderNodeMapRange');chip_mask.clamp=True
        chip_mask.inputs['From Min'].default_value=.73;chip_mask.inputs['From Max'].default_value=.81
        chip_mask.inputs['To Max'].default_value=.5*p['finish_marks']
        links.new(chips.outputs['Fac'],chip_mask.inputs['Value'])
        chipped=nodes.new('ShaderNodeMixRGB');chipped.name='Faint handling flecks'
        links.new(chip_mask.outputs[0],chipped.inputs[0]);links.new(speck_mix.outputs[0],chipped.inputs[1])
        chipped.inputs[2].default_value=(.38,.27,.18,1)
        # Outward-facing cylindrical UVs: -theta gives a right-handed surface
        # basis with +Y. +theta mirrored the F and every other glyph.
        split=nodes.new('ShaderNodeSeparateXYZ');links.new(coords.outputs['Object'],split.inputs[0])
        angle=nodes.new('ShaderNodeMath');angle.operation='ARCTAN2'
        links.new(split.outputs['Z'],angle.inputs[0]);links.new(split.outputs['X'],angle.inputs[1])
        u=nodes.new('ShaderNodeMath');u.name='Outward readable cylindrical printing';u.operation='MULTIPLY_ADD';u.inputs[1].default_value=-1/6.283185307
        print_rng=random.Random(seed+93)
        # The photograph has separate brand/size bands around the tube, not a
        # repeated two-line label. Different roll registrations expose each band.
        print_band=.75 if print_rng.random()<.55 else .50
        u.inputs[2].default_value=print_band+.25+print_rng.uniform(-.065,.065)
        links.new(angle.outputs[0],u.inputs[0])
        wrapped=nodes.new('ShaderNodeMath');wrapped.operation='FRACT';wrapped.name='Printing around full circumference'
        links.new(u.outputs[0],wrapped.inputs[0])
        v=nodes.new('ShaderNodeMath');v.operation='MULTIPLY_ADD'
        v.inputs[1].default_value=print_rng.uniform(.98,1.02)/2.405;v.inputs[2].default_value=1.055/2.405+print_rng.uniform(-.025,.025)
        links.new(split.outputs['Y'],v.inputs[0])
        uv=nodes.new('ShaderNodeCombineXYZ');links.new(wrapped.outputs[0],uv.inputs['X']);links.new(v.outputs[0],uv.inputs['Y'])
        path=Path(__file__).parent/'flashlight_lab'/'assets'/'body_print_v3.png'
        image=bpy.data.images.load(str(path),check_existing=True);image.colorspace_settings.name='Non-Color'
        if not image.packed_file:image.pack()
        ink=nodes.new('ShaderNodeTexImage');ink.name='Worn reference body printing';ink.image=image;ink.extension='CLIP'
        links.new(uv.outputs[0],ink.inputs['Vector'])
        ink_wear=p.get('plastic_ink_wear',POLYMER_DEFAULTS['plastic_ink_wear']) if controlled else 1.
        fade=nodes.new('ShaderNodeMath');fade.name='Printed ink density';fade.operation='MULTIPLY';fade.inputs[1].default_value=.98-ink_wear*(.98-print_rng.uniform(.65,.85))
        links.new(ink.outputs['Color'],fade.inputs[0])
        pressure=noise('Uneven ink transfer pressure',(17,8,17),2)
        ink_loss=nodes.new('ShaderNodeMapRange');ink_loss.clamp=True
        ink_loss.inputs['From Min'].default_value=.35;ink_loss.inputs['From Max'].default_value=.73
        ink_loss.inputs['To Min'].default_value=1;ink_loss.inputs['To Max'].default_value=1-.55*ink_wear
        links.new(pressure.outputs['Fac'],ink_loss.inputs['Value'])
        worn=nodes.new('ShaderNodeMath');worn.operation='MULTIPLY'
        links.new(fade.outputs[0],worn.inputs[0]);links.new(ink_loss.outputs[0],worn.inputs[1])
        printed=nodes.new('ShaderNodeMixRGB');printed.name='Ink on polymer'
        links.new(worn.outputs[0],printed.inputs[0]);links.new(chipped.outputs[0],printed.inputs[1])
        printed.inputs[2].default_value=(.0025,.0018,.0015,1)
        links.new(printed.outputs[0],shader.inputs['Base Color'])
        ink_rough=nodes.new('ShaderNodeMixRGB');ink_rough.name='Matte worn printing'
        links.new(worn.outputs[0],ink_rough.inputs[0]);links.new(rough_grain.outputs[0],ink_rough.inputs[1])
        ink_rough.inputs[2].default_value=(.58,.58,.58,1)
        links.new(ink_rough.outputs[0],shader.inputs['Roughness'])
        # The photo's black stamp suppresses the lamp reflection. Merely
        # darkening diffuse color left the lettering blue-grey under the bars.
        ink_specular=nodes.new('ShaderNodeMath');ink_specular.operation='MULTIPLY_ADD'
        ink_specular.name='Matte reference ink reflection'
        base_specular=shader.inputs['Specular IOR Level'].default_value
        ink_specular.inputs[1].default_value=-.7*base_specular
        ink_specular.inputs[2].default_value=base_specular
        links.new(worn.outputs[0],ink_specular.inputs[0]);links.new(ink_specular.outputs[0],shader.inputs['Specular IOR Level'])
        ink_coat=nodes.new('ShaderNodeMath');ink_coat.operation='MULTIPLY_ADD'
        ink_coat.name='Stamp interrupts glossy coating'
        base_coat=shader.inputs['Coat Weight'].default_value
        ink_coat.inputs[1].default_value=-base_coat;ink_coat.inputs[2].default_value=base_coat
        links.new(worn.outputs[0],ink_coat.inputs[0]);links.new(ink_coat.outputs[0],shader.inputs['Coat Weight'])
        mat['inspection_body_print_version']=3
        mat['inspection_body_print_text']='FEDERAL | 2¾" 70mm'
        mat['inspection_body_print_source']='Ink shapes sampled from supplied overhead reference'
        mat['inspection_body_print_visible_band']='FEDERAL' if print_band==.75 else '2¾" 70mm'
        mat['inspection_body_print_orientation']='Unmirrored exterior lettering; F starts at brass end'
        if rib_spec:
            normal,polish,finish=groove_finish(mat,coords.outputs['Object'],bump.outputs[0],ink_rough.outputs[0],printed.outputs[0],p,rib_spec)
            links.new(normal,shader.inputs['Normal']);links.new(normal,shader.inputs['Coat Normal'])
            links.new(polish,shader.inputs['Roughness']);links.new(finish,shader.inputs['Base Color'])
            shader.inputs['Coat Roughness'].default_value=.35 if controlled else .24
    if not body:
        # Tool contact smooths the folded end more than the ribbed tube wall.
        # Narrow reflections expose the crease shoulders instead of broad halos.
        if not controlled:
            rough.inputs['To Min'].default_value*=.72
            rough.inputs['To Max'].default_value*=.78
        shader.inputs['Coat Roughness'].default_value=.3 if controlled else .20
        bump.inputs['Strength'].default_value*=.45
    surface_dust(mat,p,seed)
    if body:
        rest=nodes.new('ShaderNodeAttribute');rest.attribute_name='inspection_rest_position'
        rest.name='Material follows deformed plastic'
        for node in list(nodes):
            if node.type=='TEX_COORD':
                for link in list(node.outputs['Object'].links):links.new(rest.outputs['Vector'],link.to_socket)
    return mat
