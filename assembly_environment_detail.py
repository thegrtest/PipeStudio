"""Procedural fixture refinement from the cam3936 reference photographs."""
import math


def refine_fixture_detail(scene):
    import bpy
    from mathutils import Vector,Matrix
    from assembly_scene import PREFIX,mesh
    camera=scene.camera;rotation=camera.matrix_world
    def point(px,py,depth):
        unit=depth*camera.data.sensor_width/camera.data.lens/1920
        return rotation@Vector(((px-960+camera.data.shift_x*1920)*unit,(600-py+camera.data.shift_y*1920)*unit,-depth))
    start=Vector((-180,-15));end=Vector((2110,425));axis=(end-start).normalized();cross=Vector((-axis.y,axis.x))
    def rail_depth(pixel):
        offset=(Vector(pixel)-start).dot(cross)/75
        return 58-.64*max(0,1-offset*offset)
    # Curved crown catches a localized golden reflection, instead of the
    # uniform cream rectangle produced by a completely flat front face.
    rail=bpy.data.objects[PREFIX+'Upper brass rail'];verts=[];faces=[]
    for i in range(9):
        center=start+(end-start)*(i/8)
        for j in range(25):
            pixel=center+cross*((j/24-.5)*150)
            verts.append(point(*pixel,rail_depth(pixel)))
    for i in range(8):
        for j in range(24):
            a=i*25+j;faces.append((a,a+25,a+26,a+1))
    mat=rail.data.materials[0];old=rail.data
    data=bpy.data.meshes.new(PREFIX+'Crowned rail skin');data.from_pydata(verts,[],faces);data.update();data.materials.append(mat)
    rail.data=data;rail.matrix_world=Matrix.Identity(4);rail.modifiers.clear()
    for face in data.polygons:face.use_smooth=True
    if not old.users:bpy.data.meshes.remove(old)
    n=mat.node_tree.nodes;links=mat.node_tree.links
    shader=n.get('Principled BSDF');shader.inputs['Metallic'].default_value=.94
    texture=next(v for v in n if v.type=='TEX_NOISE')
    coordinates=next(v for v in n if v.type=='TEX_COORD')
    links.new(coordinates.outputs['Object'],texture.inputs['Vector']);texture.inputs['Scale'].default_value=46
    ramp=next(v for v in n if v.type=='VALTORGB').color_ramp
    ramp.elements[0].color=(.30,.17,.036,1);ramp.elements[1].color=(.59,.38,.10,1)
    rough=next(v for v in n if v.type=='MAP_RANGE');rough.inputs['To Min'].default_value=.25;rough.inputs['To Max'].default_value=.38
    bump=next(v for v in n if v.type=='BUMP');bump.inputs['Distance'].default_value=.0012
    bpy.data.objects[PREFIX+'Rail reflection softbox'].data.energy=1100
    # Keep wear attached to the curved surface, and eliminate floating marks.
    inverse=camera.matrix_world.inverted()
    for obj in scene.objects:
        if not obj.name.startswith(PREFIX+'Rail wear '):continue
        for vertex in obj.data.vertices:
            p=inverse@(obj.matrix_world@vertex.co);unit=-p.z*camera.data.sensor_width/camera.data.lens/1920
            pixel=(p.x/unit+960-camera.data.shift_x*1920,600-p.y/unit+camera.data.shift_y*1920)
            if abs((Vector(pixel)-start).dot(cross))>73:obj.hide_render=True
            vertex.co=obj.matrix_world.inverted()@point(*pixel,rail_depth(pixel)-.006)
    # The real fastener has rounded, tapering strip ends, not hollow pipe ends.
    pale=bpy.data.objects[PREFIX+'Fastener'].data.materials[0]
    pale.node_tree.nodes.get('Principled BSDF').inputs['Base Color'].default_value=(.36,.38,.36,1)
    for name in ('Fastener rounded tail','Fastener upper tail'):bpy.data.objects[PREFIX+name].hide_render=True
    def strip(name,pixels,depth):
        front=[point(x,y,depth) for x,y in pixels];back=[point(x,y,depth+.045) for x,y in pixels];count=len(front)
        faces=[tuple(range(count)),tuple(range(2*count-1,count-1,-1))]
        faces.extend((i,(i+1)%count,(i+1)%count+count,i+count) for i in range(count))
        return mesh(name,front+back,faces,pale)
    strip('Rounded nylon lower tail',[(697,231),(701,219),(714,214),(751,217),(911,253),(1454,342),(1507,350),(1492,369),(1469,379),(1429,377),(906,289),(738,258),(711,246)],57.2)
    strip('Rounded nylon upper tail',[(734,185),(744,175),(769,175),(909,204),(941,226),(924,242),(900,235),(753,211),(734,198)],57.25)
    toward_camera=camera.matrix_world.to_quaternion()@Vector((0,0,1))
    for obj in scene.objects:
        if obj.name.startswith(PREFIX+'Fine fastener tooth '):obj.location+=toward_camera*.13
    # Fine grain plus broad low-contrast scattering variation across the bed.
    mat=bpy.data.materials[PREFIX+'Teal track'];n=mat.node_tree.nodes;link=mat.node_tree.links.new
    fine=next(v for v in n if v.type=='VALTORGB')
    fine.color_ramp.elements[0].color=(.006,.038,.065,1);fine.color_ramp.elements[1].color=(.018,.076,.13,1)
    noise=n.new('ShaderNodeTexNoise');noise.name='Broad track wear';noise.inputs['Scale'].default_value=.065;noise.inputs['Detail'].default_value=2
    link(next(v for v in n if v.type=='TEX_COORD').outputs['Object'],noise.inputs['Vector'])
    variation=n.new('ShaderNodeMapRange');variation.inputs['To Min'].default_value=.88;variation.inputs['To Max'].default_value=1.04
    link(noise.outputs['Fac'],variation.inputs[0])
    mix=n.new('ShaderNodeMixRGB');mix.blend_type='MULTIPLY';mix.inputs[0].default_value=1
    link(fine.outputs[0],mix.inputs[1]);link(variation.outputs[0],mix.inputs[2])
    for shader in n:
        if shader.type=='BSDF_DIFFUSE':link(mix.outputs[0],shader.inputs['Color'])
        elif shader.type=='BSDF_PRINCIPLED':link(mix.outputs[0],shader.inputs['Base Color'])
        elif shader.type=='BUMP':shader.inputs['Strength'].default_value=.035;shader.inputs['Distance'].default_value=.00015
        elif shader.type=='MIX_SHADER':shader.inputs[0].default_value=.08
    support=bpy.data.materials[PREFIX+'Foreground brushed support']
    for node in support.node_tree.nodes:
        if node.type=='MIX_SHADER':node.inputs[0].default_value=.42
    scene['assembly_environment_revision']='cam3936-detail-v3'
