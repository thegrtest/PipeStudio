"""Native Blender scene for a nonfunctional brass/copper visual assembly.

Uses the production brass material and deformation library, in an isolated
scene. Four real area lights make the reflection lines; none are painted on.
"""
import math
from pathlib import Path
import random
import sys

ROOT=Path(__file__).resolve().parent
if str(ROOT) not in sys.path: sys.path.insert(0,str(ROOT))

import bpy
import numpy as np
from mathutils import Vector, Quaternion

from assembly_plan import NATIVE_SIZE
from assembly_geometry import build_assembly_body
from brass_material import build_brass, update_brass
from pipe_studio import configure_renderer, aim

PREFIX='Assembly_'


def material(name,color,metallic=0,roughness=.4):
    mat=bpy.data.materials.new(PREFIX+name);mat.use_nodes=True
    n=mat.node_tree.nodes; link=mat.node_tree.links.new
    bsdf=n.get('Principled BSDF'); bsdf.inputs['Base Color'].default_value=(*color,1)
    bsdf.inputs['Metallic'].default_value=metallic;bsdf.inputs['Roughness'].default_value=roughness
    tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=22;tex.inputs['Detail'].default_value=3
    coords=n.new('ShaderNodeTexCoord');link(coords.outputs['Object'],tex.inputs['Vector'])
    bump=n.new('ShaderNodeBump');bump.inputs['Strength'].default_value=.14;bump.inputs['Distance'].default_value=.002
    link(tex.outputs['Fac'],bump.inputs['Height']);link(bump.outputs['Normal'],bsdf.inputs['Normal'])
    r=n.new('ShaderNodeMapRange');r.inputs['To Min'].default_value=max(.015,roughness-.07)
    r.inputs['To Max'].default_value=min(.95,roughness+.09)
    link(tex.outputs['Fac'],r.inputs['Value']);link(r.outputs[0],bsdf.inputs['Roughness'])
    mat.diffuse_color=(*color,1)
    return mat


def mesh(name,vertices,faces,mat,parent=None):
    data=bpy.data.meshes.new(PREFIX+name);data.from_pydata(vertices,[],faces);data.update()
    obj=bpy.data.objects.new(PREFIX+name,data);bpy.context.scene.collection.objects.link(obj)
    obj.data.materials.append(mat)
    if parent:obj.parent=parent
    return obj


def box(name,location,scale,mat,bevel=0):
    bpy.ops.mesh.primitive_cube_add(size=1,location=location)
    obj=bpy.context.object;obj.name=PREFIX+name;obj.dimensions=scale
    bpy.ops.object.transform_apply(location=False,rotation=False,scale=True)
    obj.data.materials.append(mat)
    if bevel:
        m=obj.modifiers.new('Rounded worn edges','BEVEL');m.width=bevel;m.segments=3
    return obj


def lathe(name,knots,mat,parent):
    # Closed exterior only. No internal functional assembly detail.
    n=128;verts=[];faces=[]
    for x,r in knots:
        verts.extend((x,r*math.cos(j*math.tau/n),r*math.sin(j*math.tau/n)) for j in range(n))
    for k in range(len(knots)-1):
        for j in range(n):
            q=(j+1)%n;a=k*n+j;b=(k+1)*n+j;c=(k+1)*n+q;d=k*n+q
            faces.append((a,d,c,b))
    faces.append(tuple(range(n-1,-1,-1)));faces.append(tuple((len(knots)-1)*n+j for j in range(n)))
    obj=mesh(name,verts,faces,mat,parent)
    for poly in obj.data.polygons:poly.use_smooth=len(poly.vertices)==4
    return obj


def make_environment(scene,recipe):
    teal=material('Teal track',(.007,.055,.100),.06,.38)
    teal.node_tree.nodes.get('Principled BSDF').inputs['Specular IOR Level'].default_value=.22
    # The reference bed is colored through its surface scattering; a pure
    # grazing Principled lobe washed it out into a grey mirror in this view.
    n=teal.node_tree.nodes;link=teal.node_tree.links.new
    diffuse=n.new('ShaderNodeBsdfDiffuse');diffuse.inputs['Color'].default_value=(.014,.055,.100,1)
    diffuse.inputs['Roughness'].default_value=.35
    mixed=n.new('ShaderNodeMixShader');mixed.inputs[0].default_value=.18
    link(diffuse.outputs[0],mixed.inputs[1]);link(n.get('Principled BSDF').outputs[0],mixed.inputs[2]);link(mixed.outputs[0],n.get('Material Output').inputs['Surface'])
    dark=material('Dark track frame',(.010,.018,.022),.55,.38)
    steel=material('Brushed frame',(.24,.28,.30),.85,.30)
    brass=material('Worn upper rail',(.67,.43,.15),.70,.40)
    n=brass.node_tree.nodes;link=brass.node_tree.links.new
    coords=next(v for v in n if v.type=='TEX_COORD')
    texture=next(v for v in n if v.type=='TEX_NOISE')
    stretch=n.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY';stretch.inputs[1].default_value=(28,.20,16)
    link(coords.outputs['Object'],stretch.inputs[0]);link(stretch.outputs[0],texture.inputs['Vector']);texture.inputs['Scale'].default_value=1
    colors=n.new('ShaderNodeValToRGB');colors.color_ramp.elements[0].color=(.24,.14,.035,1)
    colors.color_ramp.elements[1].color=(.85,.62,.25,1)
    link(texture.outputs['Fac'],colors.inputs[0]);link(colors.outputs[0],n.get('Principled BSDF').inputs['Base Color'])
    next(v for v in n if v.type=='BUMP').inputs['Distance'].default_value=.012
    white=material('Translucent fastener',(.56,.59,.56),0,.62)
    box('Teal bed',(0,0,-.15),(75,180,.3),teal,.04)
    box('Upper brass rail',(-1,0,9.8),(1.30,160,1.50),brass,.15)
    box('Upper dark recess',(-.5,0,7.3),(1.6,160,.8),dark,.08)
    box('LED housing',(0,0,5.5),(.48,160,.36),steel,.05)
    strip=material('Warm diffuser',(.6,.48,.30),0,.42)
    shader=strip.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Emission Color'].default_value=(1,.69,.34,1)
    shader.inputs['Emission Strength'].default_value=.35
    box('Visible diffuser',(0,-.08,5.69),(.24,160,.035),strip,.014)
    box('Lower frame',(-5,0,-.10),(.60,160,.44),dark,.10)
    # Transparent end guide: the assembly's brass end stays at X=3.3.
    glass=material('Clear guide',(.96,.99,1),0,.055)
    shader=glass.node_tree.nodes.get('Principled BSDF')
    shader.inputs['Transmission Weight'].default_value=1
    shader.inputs['IOR'].default_value=1.46
    guide=box('Transparent guide',(3.40,0,.70),(.13,160,1.40),glass,.012)
    guide['annotation_transparent']=True
    box('Guide lower edge',(3.40,0,.025),(.20,160,.05),dark,.01)
    # Sparse rail scuffs and the pale retained cable-tie shape seen above it.
    tie=box('Fastener',(-1.20,-1,8.44),(.20,8,.21),white,.1)
    for i in range(27):
        box(f'Fastener rib {i}',(-1.32,-4.4+i*.25,8.51),(.025,.024,.16),white,.007)
    rng=random.Random(615)
    for i in range(18):
        obj=box(f'Rail scuff {i}',(-1.53,rng.uniform(-13,13),rng.uniform(8.76,9.20)),
                (.002,rng.uniform(.25,1.3),.015),steel)
        obj.rotation_euler.x=rng.uniform(-.6,.6)
    env=recipe['environment']
    # Spread across the cylindrical cross-section; long dimension follows
    # the brass axis. Four emitters remain physically present in every frame.
    for i,(y,z) in enumerate(((-100,25),(-36,35),(7,40),(70,30))):
        data=bpy.data.lights.new(PREFIX+f'Light bar {i+1}','AREA')
        data.shape='RECTANGLE';data.size=125;data.size_y=.8
        data.energy=11250*env['light_scale']*env['bar_balance'][i]
        data.color=(1,.94,.82)
        light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light)
        light.location=(0,y+env['light_shift'],z);aim(light,(0,0,.62))
        light['reflection_bar_index']=i
    data=bpy.data.lights.new(PREFIX+'Ambient fill','AREA');data.shape='DISK';data.size=28;data.energy=450
    light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light)
    light.location=(-12,-15,16);aim(light,(0,0,0));data.color=(.61,.79,1)
    data=bpy.data.lights.new(PREFIX+'Rail bounce','AREA');data.shape='RECTANGLE';data.size=60;data.size_y=9;data.energy=2200
    light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light)
    light.location=(-10,0,14);aim(light,(-1,0,8));data.color=(1,.93,.82)
    world=bpy.data.worlds.new(PREFIX+'World');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.16,.20,.24,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.18
    scene.world=world


def initialize_scene(recipe,samples=96,scale=1):
    # Light-link collections can retain objects after scene deletion. Remove
    # our receivers and objects explicitly so later builds never resolve an
    # old rail/material by name while rendering a newly suffixed object.
    for collection in list(bpy.data.collections):
        if collection.name.startswith(PREFIX):bpy.data.collections.remove(collection)
    for obj in list(bpy.data.objects):
        if obj.name.startswith(PREFIX):bpy.data.objects.remove(obj,do_unlink=True)
    bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
    scene=bpy.context.scene;scene.name='Inert assembly inspection'
    for key in ('assembly_background_source','assembly_background_mode','assembly_camera_elevation_deg','assembly_camera_fit','assembly_fill_receiver'):
        if key in scene:del scene[key]
    scene.compositing_node_group=None
    for material_ in list(bpy.data.materials):
        if material_.users==0:bpy.data.materials.remove(material_)
    for data in list(bpy.data.meshes):
        if data.users==0:bpy.data.meshes.remove(data)
    for data in list(bpy.data.images):
        if data.users==0:bpy.data.images.remove(data)
    for blocks in (bpy.data.lights,bpy.data.cameras,bpy.data.curves,bpy.data.worlds):
        for data in list(blocks):
            if data.users==0 and data.name.startswith(PREFIX):blocks.remove(data)
    configure_renderer(scene)
    scene.cycles.samples=samples;scene.cycles.preview_samples=32
    scene.cycles.max_bounces=8;scene.cycles.transmission_bounces=6
    scene.render.use_persistent_data=False
    scene.render.resolution_x=NATIVE_SIZE[0]*scale;scene.render.resolution_y=NATIVE_SIZE[1]*scale
    scene.render.image_settings.color_mode='RGB'
    scene.view_settings.view_transform='AgX';scene.view_settings.exposure=recipe['environment']['exposure']
    return scene


def make_assembly(scene,recipe):
    rig=bpy.data.objects.new(PREFIX+'Rolling specimen',None);scene.collection.objects.link(rig)
    rig.rotation_euler.z=math.pi
    mat=bpy.data.materials.new(PREFIX+'Shared drawn brass');mat.use_nodes=True
    build_brass(mat);update_brass(mat,recipe['finish'])
    # Finished assembly has a more burnished surface than the upstream dull
    # camera station. Keep its grain/oxide maps but narrow reflection lobes.
    nodes=mat.node_tree.nodes
    nodes['RoughnessBase'].outputs[0].default_value=recipe['finish']['roughness']*.76
    nodes['PolishedBrass'].inputs['Roughness'].default_value=.18
    nodes['Inspection grain roughness'].inputs['To Min'].default_value=.045
    nodes['Inspection grain roughness'].inputs['To Max'].default_value=-.045
    from assembly_realism import configure_surface
    configure_surface(mat,recipe)
    verts,faces,supports=build_assembly_body(recipe)
    body=mesh('Shell',verts,faces,mat,rig);body['part_class_id']=0
    for p in body.data.polygons:p.use_smooth=True
    for i,support in enumerate(supports):
        attr=body.data.attributes.new(f'defect_{i}','FLOAT','POINT');attr.data.foreach_set('value',support)
    # Diagnostic scratches expose brass along the groove while preserving the
    # surrounding shared alloy and local grain. Cosmetic scuffs stay unlabeled.
    scratch_indices=[i for i,v in enumerate(recipe['instances']) if v['kind']=='scratch']
    if scratch_indices:
        n=mat.node_tree.nodes;link=mat.node_tree.links.new
        out=next(v for v in n if v.type=='OUTPUT_MATERIAL');source=out.inputs['Surface'].links[0].from_socket
        for i in scratch_indices:
            attr=n.new('ShaderNodeAttribute');attr.attribute_name=f'defect_{i}'
            clean=n.new('ShaderNodeBsdfPrincipled');clean.inputs['Base Color'].default_value=(.9,.68,.27,1)
            clean.inputs['Metallic'].default_value=1;clean.inputs['Roughness'].default_value=.24
            mix=n.new('ShaderNodeMixShader');link(attr.outputs['Fac'],mix.inputs[0]);link(source,mix.inputs[1]);link(clean.outputs[0],mix.inputs[2]);source=mix.outputs[0]
        link(source,out.inputs['Surface'])
    radius=recipe['base']['radius'];length=recipe['base']['length']
    cap=lathe('Shell end',[(-length/2-.035,radius*.95),(-length/2,radius),(-length/2+.075,radius*.99)],mat,rig)
    cap['part_class_id']=0
    # A smooth visual insert, exterior only. Inferred photographic proportions.
    copper=material('Copper ferrule',(.66,.28,.125),.97,.27)
    s=length/2
    knots=[(s-.16,radius*.61),(s+.16,radius*.61),(s+.30,radius*.58),
           (s+.64,radius*.53),(s+1.02,radius*.44),(s+1.38,radius*.34),
           (s+1.75,radius*.23),(s+2.08,radius*.12),(s+2.23,radius*.052),(s+2.27,radius*.016)]
    ferrule=lathe('Ferrule',knots,copper,rig);ferrule['part_class_id']=1
    # Full-resolution reference shows a shorter exposed copper insert.
    for vertex in ferrule.data.vertices:
        vertex.co.x=s+(vertex.co.x-s)*.70
    for obj in rig.children:obj['specimen_id']=recipe['specimen_id']
    if recipe.get('look','ORIGINAL') in ('REFINED','CAMERA_MATCHED'):
        from assembly_realism import refine_part
        refine_part(scene,rig,body,recipe)
    return rig,body


def build_scene(recipe,samples=96,scale=1):
    scene=initialize_scene(recipe,samples,scale)
    rig,body=make_assembly(scene,recipe)
    make_environment(scene,recipe)
    data=bpy.data.cameras.new(PREFIX+'Camera');camera=bpy.data.objects.new(data.name,data);scene.collection.objects.link(camera)
    refined=recipe.get('look','ORIGINAL') in ('REFINED','CAMERA_MATCHED')
    camera.location=(-22,-40,7.0);aim(camera,(-.8,0,2.5 if refined else 3.4))
    camera.rotation_euler=(camera.rotation_euler.to_quaternion() @ Quaternion((0,0,1),math.radians(6 if refined else 2.5))).to_euler()
    data.type='PERSP';data.lens=62 if refined else 55;data.sensor_width=36;data.shift_x=.08 if refined else .15;data.clip_end=500
    scene.camera=camera
    if recipe.get('look')=='CAMERA_MATCHED':
        from assembly_camera_match import configure_camera
        configure_camera(scene,camera)
    bpy.context.view_layer.update()
    fit_reference_fixtures(scene)
    from assembly_realism import refine_environment,configure_lights
    if refined:refine_environment(scene,recipe)
    configure_lights(scene,recipe)
    scene['assembly_recipe_seed']=recipe['seed']
    scene['assembly_geometry_units']='Inferred exterior proportions; arbitrary scene units'
    from camera_response import configure_camera_response
    configure_camera_response(scene,dict(environment='STUDIO',camera_softness=.5,resolution=scene.render.resolution_x))
    tree=scene.compositing_node_group
    softness_scale=1.5 if recipe.get('look')=='CAMERA_MATCHED' else 2.4
    tree.nodes['PS_CR_Lens'].inputs['Size'].default_value=(recipe['environment']['softness_px']*softness_scale*scale*3,)*2
    tree.nodes['PS_CR_Lens'].mute=False;tree.nodes['PS_CR_Highlights'].mute=True
    scene.render.use_compositing=True
    if recipe.get('look')=='CAMERA_MATCHED':
        from assembly_camera_match import configure_plate
        configure_plate(scene,recipe)
    return scene,rig,body


def fit_reference_fixtures(scene):
    """3D fixture layout constrained by lines in the native reference frames.

    Single-view fixture depth is underdetermined. These are editable inferred
    extrinsics, preserving the measured projection, not measured CAD geometry.
    """
    from mathutils import Matrix
    camera=scene.camera;depth=58.0
    units=depth*camera.data.sensor_width/camera.data.lens/1920
    def point(x,y):
        return camera.matrix_world @ Vector(((x-960+camera.data.shift_x*1920)*units,(600-y+camera.data.shift_y*1920)*units,-depth))
    def fit(name,start,end,width,thickness=.25,forward=0):
        obj=bpy.data.objects[PREFIX+name];a=point(*start);b=point(*end)
        direction=(b-a).normalized();normal=camera.matrix_world.to_quaternion() @ Vector((0,0,1))
        perpendicular=direction.cross(normal).normalized()
        obj.location=(a+b)/2+normal*forward
        obj.rotation_euler=Matrix((perpendicular,direction,normal)).transposed().to_euler()
        obj.dimensions=(width*units,(b-a).length,thickness)
        return obj
    fit('Upper brass rail',(-180,-15),(2110,425),150)
    fit('Upper dark recess',(-180,95),(2110,535),84)
    fit('LED housing',(-180,124),(2110,739),80)
    fit('Visible diffuser',(-180,120),(2110,735),23,.045,.16)
    diode=material('Diffuser diodes',(.63,.36,.15),0,.62)
    diode.node_tree.nodes.get('Principled BSDF').inputs['Emission Color'].default_value=(1,.57,.18,1)
    diode.node_tree.nodes.get('Principled BSDF').inputs['Emission Strength'].default_value=.35
    for i in range(105):
        name=f'Diffuser segment {i}'
        box(name,(0,0,0),(1,1,1),diode,.04)
        x=-100+i*20;y=120+(x+180)*615/2290
        fit(name,(x-5,y-1.4),(x+5,y+1.4),12,.035,.20)
    fit('Fastener',(700,226),(1500,370),52,.30,.32)
    for i in range(27):
        x=915+i*20;y=265+(x-915)*.18
        fit(f'Fastener rib {i}',(x,y-13),(x,y+13),4,.035,.51)
    rng=random.Random(615)
    for i in range(18):
        x=rng.uniform(740,1380);y=50+x*.192+rng.uniform(-25,30)
        fit(f'Rail scuff {i}',(x,y),(x+rng.uniform(-55,50),y+rng.uniform(15,60)),rng.uniform(.7,1.7),.012,.15)


def pose_scene(scene,rig,body,recipe,pose):
    rig.rotation_euler=(pose['roll'],0,math.pi)
    rig.location=(0,pose['travel'],recipe['base']['radius'])
    if recipe.get('look')=='CAMERA_MATCHED':
        from assembly_camera_match import track_position
        rig.location.x,rig.location.y=track_position(scene,pose['travel'])
        pose['placement_model']='Image-constrained track corridor; nominal roll, inferred exterior geometry'
        pose['guide_clearance']=None
    bpy.context.view_layer.update()
    # Raise a distorted shell only enough to stay on the track; fixed end
    # guide contact and nominal rolling radius remain explicit in metadata.
    minimum=min((obj.matrix_world @ v.co).z for obj in rig.children if obj.type=='MESH' for v in obj.data.vertices)
    rig.location.z-=minimum
    bpy.context.view_layer.update()
    pose['actual_center_height']=float(rig.location.z)
    pose['actual_location']=list(rig.location)
    scene['assembly_current_pose']=str(pose)


def diagnostic_material(name,attribute=None,white=False,transparent=False):
    mat=bpy.data.materials.new(PREFIX+name);mat.use_nodes=True
    n=mat.node_tree.nodes;n.clear();link=mat.node_tree.links.new
    out=n.new('ShaderNodeOutputMaterial')
    shader=n.new('ShaderNodeBsdfTransparent' if transparent else 'ShaderNodeEmission')
    if not transparent:shader.inputs['Color'].default_value=(1,1,1,1) if white else (0,0,0,1)
    if attribute:
        attr=n.new('ShaderNodeAttribute');attr.attribute_name=attribute
        gate=n.new('ShaderNodeMath');gate.operation='GREATER_THAN';gate.inputs[1].default_value=.5
        link(attr.outputs['Fac'],gate.inputs[0]);link(gate.outputs[0],shader.inputs['Color'])
    link(shader.outputs[0],out.inputs['Surface']);return mat


def render_masks(scene,body,recipe,folder,stem):
    """Silhouette/support masks with opaque occlusion and clear-guide transmission.

    The clear plate is treated as transparent for geometric labels, avoiding
    reflection ghosts. Optics, glare, noise and DOF never contaminate masks.
    """
    from camera_response import set_diagnostic_mode
    from domain_render import read_display_raster
    saved={o: list(o.data.materials) for o in scene.objects if o.type=='MESH'}
    catcher_state={o:o.is_shadow_catcher for o in saved}
    transparent_state=scene.render.film_transparent
    state=(scene.view_settings.view_transform,scene.view_settings.exposure,scene.cycles.samples,scene.cycles.use_denoising,scene.world)
    black=diagnostic_material('Mask black');white=diagnostic_material('Mask white',white=True)
    clear=diagnostic_material('Mask clear',transparent=True)
    maskworld=bpy.data.worlds.new(PREFIX+'Mask world');maskworld.use_nodes=True
    maskworld.node_tree.nodes['Background'].inputs[1].default_value=0
    results={}
    try:
        set_diagnostic_mode(scene,True)
        scene.render.film_transparent=False
        for obj in saved:obj.is_shadow_catcher=False
        scene.world=maskworld;scene.view_settings.view_transform='Standard';scene.view_settings.exposure=0
        scene.cycles.samples=8;scene.cycles.use_denoising=False
        requests=[('shell',0,None),('ferrule',1,None)]+[(f'defect_{i}',None,f'defect_{i}') for i in range(len(recipe['instances']))]
        for name,part,attribute in requests:
            target=diagnostic_material('Support '+name,attribute=attribute) if attribute else white
            for obj in saved:
                mat=clear if obj.get('annotation_transparent') else black
                if part is not None and obj.get('part_class_id',-1)==part and obj.get('specimen_id')==recipe['specimen_id']:mat=white
                if attribute and obj==body:mat=target
                obj.data.materials.clear();obj.data.materials.append(mat)
            scene.render.filepath=str(folder/f'{stem}_{name}.png')
            bpy.ops.render.render(write_still=True)
            results[name]=read_display_raster(scene.render.filepath)[:,:,0]>.5
            if attribute:bpy.data.materials.remove(target)
    finally:
        for obj,mats in saved.items():
            obj.data.materials.clear()
            for mat in mats:obj.data.materials.append(mat)
        scene.view_settings.view_transform,scene.view_settings.exposure,scene.cycles.samples,scene.cycles.use_denoising,scene.world=state
        set_diagnostic_mode(scene,False)
        scene.render.film_transparent=transparent_state
        for obj,value in catcher_state.items():obj.is_shadow_catcher=value
        for mat in (black,white,clear):bpy.data.materials.remove(mat)
        bpy.data.worlds.remove(maskworld)
    return results
