"""Procedural assembly finishes and reflection rigs, shared by three looks."""
import math
import random

LIGHTING_PRESETS=('CURRENT','FOUR_LINES','BALANCED')
LOOKS=('ORIGINAL','REFINED','CAMERA_MATCHED')


def companion_offset(recipe):
    if recipe.get('look')=='CAMERA_MATCHED':return 8.0
    return -13.0 if recipe.get('look','ORIGINAL')=='REFINED' else -18.0


def profile(name):
    if name not in LIGHTING_PRESETS:raise ValueError('Unknown assembly lighting preset')
    return {
        'CURRENT':dict(width=.8,power=11250,roughness=None,positions=((-100,25),(-36,35),(7,40),(70,30))),
        'FOUR_LINES':dict(width=.7,power=52000,roughness=(.075,.12),heights=(.82,.60,.38,.15)),
        'BALANCED':dict(width=5.2,power=45000,roughness=(.19,.26),heights=(.82,.60,.38,.15)),
    }[name]


def configure_surface(mat,recipe):
    """Mottled drawn wall, restrained oxide, darker neck and actual shader links."""
    import bpy
    n=mat.node_tree.nodes;link=mat.node_tree.links.new
    def node(kind,name):
        v=n.get(name)
        if v is None:v=n.new(kind);v.name=v.label=name
        return v
    if recipe.get('look','ORIGINAL') in ('REFINED','CAMERA_MATCHED'):
        n['OxideAmount'].outputs[0].default_value=min(.8,recipe['finish']['oxide_amount']*.7+.30)
        n['PolishAmount'].outputs[0].default_value=recipe['finish']['polish_amount']*.73
        ramp=n['OxideColors'].color_ramp
        ramp.elements[0].color=(.095,.058,.027,1);ramp.elements[1].color=(.27,.18,.080,1)
        # The copper-adjacent neck in the reference has a warm, duller band.
        neck=node('ShaderNodeMapRange','Assembly neck finishing band');neck.clamp=True;neck.interpolation_type='SMOOTHSTEP'
        neck.inputs['From Min'].default_value=recipe['base']['length']*.28
        neck.inputs['From Max'].default_value=recipe['base']['length']*.43
        neck.inputs['To Max'].default_value=.55
        link(n['Local pipe position'].outputs['X'],neck.inputs['Value'])
        for shader in ('BrassShader','PolishedBrass','DullOxide'):
            tint=node('ShaderNodeMixRGB','Assembly neck tint '+shader);tint.blend_type='MULTIPLY'
            tint.inputs[2].default_value=(.62,.47,.33,1)
            if recipe.get('look')=='CAMERA_MATCHED':
                neck.inputs['To Max'].default_value=.86
                tint.inputs[2].default_value=(.20,.12,.07,1)
            link(n['Inspection localized color '+shader].outputs[0],tint.inputs[1]);link(neck.outputs[0],tint.inputs[0]);link(tint.outputs[0],n[shader].inputs['Base Color'])
    rig=profile(recipe.get('lighting','CURRENT'))
    for shader in ('BrassShader','PolishedBrass'):
        source=n['Inspection local roughness '+shader].outputs[0]
        if rig['roughness']:
            mapped=node('ShaderNodeMapRange','Assembly reflection width '+shader);mapped.clamp=True
            mapped.inputs['From Min'].default_value=.10;mapped.inputs['From Max'].default_value=.55
            mapped.inputs['To Min'].default_value=rig['roughness'][0];mapped.inputs['To Max'].default_value=rig['roughness'][1]
            link(source,mapped.inputs[0]);source=mapped.outputs[0]
        if recipe.get('look')=='CAMERA_MATCHED':
            if recipe.get('lighting')=='BALANCED':
                # Retain broad drawn-finish variation at the smaller native
                # object size instead of compressing it out of all four bands.
                coords=node('ShaderNodeTexCoord','Assembly camera finish coordinates')
                stretch=node('ShaderNodeVectorMath','Assembly camera drawn grain');stretch.operation='MULTIPLY'
                stretch.inputs[1].default_value=(.25,2,2);link(coords.outputs['Object'],stretch.inputs[0])
                noise=node('ShaderNodeTexNoise','Assembly camera roughness patches');noise.inputs['Scale'].default_value=10
                noise.inputs['Detail'].default_value=2;link(stretch.outputs[0],noise.inputs['Vector'])
                amount=node('ShaderNodeMath','Assembly camera roughness variation');amount.operation='MULTIPLY_ADD'
                amount.inputs[1].default_value=.18;amount.inputs[2].default_value=-.09;link(noise.outputs['Fac'],amount.inputs[0])
                uneven=node('ShaderNodeMath','Assembly uneven bands '+shader);uneven.operation='ADD'
                link(source,uneven.inputs[0]);link(amount.outputs[0],uneven.inputs[1]);source=uneven.outputs[0]
            # The real neck is duller than the drawn body. Preserve the four
            # body reflections while spreading their intensity at the neck.
            extra=node('ShaderNodeMath','Assembly neck roughness amount');extra.operation='MULTIPLY'
            extra.inputs[1].default_value=.29;link(n['Assembly neck finishing band'].outputs[0],extra.inputs[0])
            local=node('ShaderNodeMath','Assembly camera roughness '+shader);local.operation='ADD'
            link(source,local.inputs[0]);link(extra.outputs[0],local.inputs[1]);source=local.outputs[0]
        link(source,n[shader].inputs['Roughness'])
    from assembly_finish import configure_finish
    configure_finish(mat,recipe)


def configure_lights(scene,recipe,multiplier=1.0):
    from pipe_studio import aim
    env=recipe['environment'];name=recipe.get('lighting','CURRENT');p=profile(name)
    # Four incident directions solve reflection about four surface normals.
    # They are real emitters; dents distort the bands rather than a 2D overlay.
    view_angle=math.atan2(scene.camera.location.z-.62,scene.camera.location.y)
    for obj in scene.objects:
        if 'reflection_bar_index' not in obj:continue
        i=obj['reflection_bar_index']
        if name=='CURRENT':
            y,z=p['positions'][i];length=125
        else:
            height=(.60,.28,-.02,-.28)[i] if recipe.get('look')=='CAMERA_MATCHED' and name=='BALANCED' else p['heights'][i]
            normal_angle=view_angle-math.asin(height)
            incoming=2*normal_angle-view_angle
            y=math.cos(incoming)*110;z=.62+math.sin(incoming)*110;length=220
        obj.location=(0,y+env['light_shift'],z);aim(obj,(0,0,.62))
        obj.data.size=length;obj.data.size_y=p['width']
        balance=1.0 if name=='FOUR_LINES' else env['bar_balance'][i]
        if recipe.get('look')=='CAMERA_MATCHED' and name=='BALANCED':
            # Isolated native patches locate bar 0 at the TOP of the body.
            # Measured row profiles show one strong band and three quieter ones.
            balance*=(10.0,.38,.30,.20)[i]
        obj.data.energy=p['power']*env['light_scale']*balance*multiplier
        obj['preset_power']=float(obj.data.energy/max(multiplier,1e-9))
    scene['assembly_lighting_preset']=name


def refine_part(scene,rig,body,recipe):
    from assembly_scene import material,lathe
    radius=recipe['base']['radius'];length=recipe['base']['length'];s=length/2
    mat=body.data.materials[0]
    cap=next(o for o in rig.children if 'Shell end' in o.name)
    ferrule=next(o for o in rig.children if o.get('part_class_id')==1)
    old=cap.data
    new=lathe('Rounded end bead',[(-s-.035,radius*.98),(-s-.024,radius*1.065),
        (-s+.025,radius*1.075),(-s+.070,radius*1.065),(-s+.10,radius*.985)],mat,rig)
    cap.data=new.data
    import bpy
    bpy.data.objects.remove(new,do_unlink=True)
    if old.users==0:bpy.data.meshes.remove(old)
    receivers=bpy.data.collections.get(scene.get('assembly_fill_receiver',''))
    if receivers:
        for obj in rig.children:
            if obj.name not in receivers.objects:receivers.objects.link(obj)
    # More rounded exterior; no pointed zero-radius cone apex.
    knots=[(s-.12,.378),(s+.06,.378),(s+.35,.367),(s+.68,.326),(s+.96,.265),
           (s+1.22,.194),(s+1.43,.125),(s+1.56,.076),(s+1.60,.045)]
    interpolated=[]
    for a,b in zip(knots,knots[1:]):
        for j in range(6):
            t=j/6;interpolated.append((a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t))
    interpolated.append(knots[-1])
    copper=ferrule.data.materials[0];n=copper.node_tree.nodes;link=copper.node_tree.links.new
    shader=n.get('Principled BSDF');shader.inputs['Base Color'].default_value=(.50,.205,.098,1)
    texture=next(v for v in n if v.type=='TEX_NOISE');texture.inputs['Scale'].default_value=105
    variation=n.new('ShaderNodeValToRGB');variation.color_ramp.elements[0].color=(.28,.09,.04,1)
    variation.color_ramp.elements[1].color=(.70,.31,.16,1)
    if recipe.get('look')=='CAMERA_MATCHED':
        variation.color_ramp.elements[0].color=(.12,.035,.016,1)
        variation.color_ramp.elements[1].color=(.30,.105,.055,1)
        texture.inputs['Scale'].default_value=28
        rough=next(v for v in n if v.type=='MAP_RANGE')
        rough.inputs['To Min'].default_value=.19;rough.inputs['To Max'].default_value=.30
        # Drawn copper has fine axial streaking in addition to broad tarnish.
        coords=next(v for v in n if v.type=='TEX_COORD')
        stretch=n.new('ShaderNodeVectorMath');stretch.operation='MULTIPLY';stretch.inputs[1].default_value=(.5,6,6)
        link(coords.outputs['Object'],stretch.inputs[0]);link(stretch.outputs[0],texture.inputs['Vector'])
    link(texture.outputs['Fac'],variation.inputs[0]);link(variation.outputs[0],shader.inputs['Base Color'])
    old=ferrule.data;new=lathe('Rounded insert',interpolated,copper,rig);ferrule.data=new.data
    bpy.data.objects.remove(new,do_unlink=True)
    if old.users==0:bpy.data.meshes.remove(old)


def refine_environment(scene,recipe):
    import bpy
    from mathutils import Vector,Matrix
    from assembly_scene import PREFIX,material,box
    from pipe_studio import aim
    camera=scene.camera
    def point(px,py,depth=58):
        u=depth*camera.data.sensor_width/camera.data.lens/1920
        return camera.matrix_world @ Vector(((px-960+camera.data.shift_x*1920)*u,(600-py+camera.data.shift_y*1920)*u,-depth))
    def fit(obj,start,end,width,depth=58,thickness=.04):
        a=point(*start,depth);b=point(*end,depth)
        y=(b-a).normalized();z=camera.matrix_world.to_quaternion() @ Vector((0,0,1));x=y.cross(z).normalized()
        obj.location=(a+b)/2;obj.rotation_euler=Matrix((x,y,z)).transposed().to_euler()
        obj.dimensions=(width*depth*camera.data.sensor_width/camera.data.lens/1920,(b-a).length,thickness)
    def stroke(name,points,mat,radius_px=1,depth=57.7):
        data=bpy.data.curves.new(PREFIX+name,'CURVE');data.dimensions='3D';data.resolution_u=2
        curve=data.splines.new('POLY');curve.points.add(len(points)-1)
        for v,xy in zip(curve.points,points):v.co=(*point(*xy,depth),1)
        data.bevel_depth=radius_px*depth*camera.data.sensor_width/camera.data.lens/1920;data.bevel_resolution=2
        obj=bpy.data.objects.new(PREFIX+name,data);scene.collection.objects.link(obj);obj.data.materials.append(mat)
        # The mask exporter handles mesh fixtures and their occlusion.
        bpy.context.view_layer.objects.active=obj;obj.select_set(True)
        bpy.ops.object.convert(target='MESH');obj.select_set(False)
        return obj
    # Replace the slab-like cable fastener with tapered/rounded ends and a
    # second thin tail as seen beneath the worn upper rail.
    pale=bpy.data.objects[PREFIX+'Fastener'].data.materials[0]
    bpy.data.objects[PREFIX+'Fastener'].hide_render=True
    for i in range(27):bpy.data.objects[PREFIX+f'Fastener rib {i}'].hide_render=True
    # Flatten the profile so these are nylon strips, not round white cables.
    tail=stroke('Fastener rounded tail',[(720,229),(745,241),(930,279),(1330,350),(1485,367)],pale,20,57.4)
    upper=stroke('Fastener upper tail',[(742,194),(790,200),(870,218),(920,238)],pale,17,57.35)
    normal=camera.matrix_world.to_quaternion() @ Vector((0,0,1))
    for obj in (tail,upper):
        center=sum((v.co for v in obj.data.vertices),Vector())/len(obj.data.vertices)
        for v in obj.data.vertices:v.co-=normal*((v.co-center).dot(normal)*.82)
    for i in range(67):
        x=914+i*8.3;y=268+(x-914)*.177
        stroke(f'Fine fastener tooth {i}',[(x,y-9),(x+1,y+9)],pale,1.1,57.22)
    # Random fine crossing wear replaces the sparse dark floating stubs.
    for i in range(18):bpy.data.objects[PREFIX+f'Rail scuff {i}'].hide_render=True
    scratch=material('Worn rail exposed scratches',(.53,.37,.13),.85,.44)
    dark=material('Fine worn rail scratches',(.15,.10,.046),.6,.65)
    rng=random.Random(7901)
    for i in range(80):
        x=rng.uniform(90,1800);y=30+x*.193+rng.uniform(-30,42)
        dx=rng.uniform(-65,65);dy=rng.uniform(-30,40)
        stroke(f'Rail wear {i}',[(x,y),(x+dx*.45,y+dy*.35),(x+dx,y+dy)],scratch if i%4 else dark,rng.uniform(.15,.35))
    rail=bpy.data.objects[PREFIX+'Upper brass rail'];mat=rail.data.materials[0];n=mat.node_tree.nodes
    shader=n.get('Principled BSDF');shader.inputs['Metallic'].default_value=.97
    ramp=next(v for v in n if v.type=='VALTORGB').color_ramp
    ramp.elements[0].color=(.48,.31,.105,1);ramp.elements[1].color=(.74,.53,.23,1)
    rough=next(v for v in n if v.type=='MAP_RANGE');rough.inputs['To Min'].default_value=.18;rough.inputs['To Max'].default_value=.32
    # Broad inspection reflection on the rail alone, using native light linking.
    data=bpy.data.lights.new(PREFIX+'Rail reflection softbox','AREA');data.shape='RECTANGLE';data.size=12;data.size_y=3;data.energy=2400
    light=bpy.data.objects.new(data.name,data);scene.collection.objects.link(light)
    light.location=point(430,20,26);aim(light,point(630,100,58));data.color=(1,.91,.77)
    receivers=bpy.data.collections.new(PREFIX+'Rail illumination receivers');receivers.objects.link(rail)
    light.light_linking.receiver_collection=receivers
    # More blue/cyan scattering, quiet patches and scuffs on the bed.
    mat=bpy.data.materials[PREFIX+'Teal track'];n=mat.node_tree.nodes;link=mat.node_tree.links.new
    noise=next(v for v in n if v.type=='TEX_NOISE');noise.inputs['Scale'].default_value=35
    ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.008,.045,.077,1)
    ramp.color_ramp.elements[1].color=(.025,.09,.15,1)
    link(noise.outputs['Fac'],ramp.inputs[0])
    for shader in n:
        if shader.type=='BSDF_DIFFUSE':link(ramp.outputs[0],shader.inputs['Color'])
    bpy.data.objects[PREFIX+'Lower frame'].hide_render=True
    # Retain contact geometry, but approximate this thin guide as transmitting.
    # The inferred slab's reflected duplicate is absent in the reference.
    # Foreground acrylic, its soft support reflection and scuffs remain visible.
    guide=bpy.data.objects[PREFIX+'Transparent guide'];guide.dimensions.x=.035;guide.location.x=3.3525
    glass=guide.data.materials[0];n=glass.node_tree.nodes;link=glass.node_tree.links.new
    out=n.get('Material Output');old=out.inputs['Surface'].links[0].from_socket
    clear=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader');mix.inputs[0].default_value=0.0
    link(clear.outputs[0],mix.inputs[1]);link(old,mix.inputs[2]);link(mix.outputs[0],out.inputs['Surface'])
    bpy.data.objects[PREFIX+'Guide lower edge'].hide_render=True
    # Foreground acrylic guard and the soft, curved support reflected in it.
    front=material('Foreground clear guard',(.035,.075,.105),0,.31)
    n=front.node_tree.nodes;link=front.node_tree.links.new;shader=n.get('Principled BSDF')
    shader.inputs['Transmission Weight'].default_value=.6;shader.inputs['IOR'].default_value=1.46
    clear=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader');mix.inputs[0].default_value=.13
    link(clear.outputs[0],mix.inputs[1]);link(shader.outputs[0],mix.inputs[2]);link(mix.outputs[0],n.get('Material Output').inputs['Surface'])
    from assembly_scene import mesh
    sheet=mesh('Foreground clear shield',[point(x,y,24) for x,y in ((-100,652),(2050,1095),(2050,1560),(-100,1560))],[(0,1,2,3)],front)
    sheet['annotation_transparent']=True
    grey=material('Foreground brushed support',(.13,.16,.19),.50,.48)
    n=grey.node_tree.nodes;link=grey.node_tree.links.new
    clear=n.new('ShaderNodeBsdfTransparent');mix=n.new('ShaderNodeMixShader');mix.inputs[0].default_value=.30
    link(clear.outputs[0],mix.inputs[1]);link(n.get('Principled BSDF').outputs[0],mix.inputs[2]);link(mix.outputs[0],n.get('Material Output').inputs['Surface'])
    curve=[(-140,954),(100,1010),(480,1100),(1000,1190),(1450,1210),(1900,1140),(2080,1100)]
    # Sample a smooth cubic path to remove polygonal bends in the guard.
    smooth=[]
    extended=[curve[0]]+curve+[curve[-1]]
    for i in range(1,len(extended)-2):
        p0,p1,p2,p3=[Vector(v) for v in extended[i-1:i+3]]
        for j in range(12):
            t=j/12;smooth.append(tuple(.5*((2*p1)+(-p0+p2)*t+(2*p0-5*p1+4*p2-p3)*t*t+(-p0+3*p1-3*p2+p3)*t*t*t)))
    stroke('Curved foreground support',smooth,grey,42,26)
    fine=material('Acrylic hairline scuffs',(.13,.18,.21),0,.7)
    for i in range(32):
        x=rng.uniform(0,1920);y=rng.uniform(760,1400)
        if y < 680+.22*x:continue
        obj=stroke(f'Guard handling trace {i}',[(x,y),(x+rng.uniform(-32,32),y+rng.uniform(-16,16))],fine,rng.uniform(.10,.22),23.95)
        obj['annotation_transparent']=True
    # Warm diffuse fill lifts tarnished areas without another narrow stripe.
    data=bpy.data.lights.new(PREFIX+'Soft oxide fill','AREA');data.shape='RECTANGLE';data.size=45;data.size_y=18;data.energy=5200
    if hasattr(data,'specular_factor'):data.specular_factor=0.0
    obj=bpy.data.objects.new(data.name,data);scene.collection.objects.link(obj);obj.location=(-15,-28,9);data.color=(1,.82,.59);aim(obj,(0,-8,.7))
    if recipe.get('look')=='CAMERA_MATCHED':
        # specular_factor alone left a fifth broad highlight in Cycles.
        obj.visible_glossy=False
        data.energy=3500
    receivers=bpy.data.collections.new(PREFIX+'Oxide fill receivers')
    for part in scene.objects:
        if 'part_class_id' in part:receivers.objects.link(part)
    obj.light_linking.receiver_collection=receivers;scene['assembly_fill_receiver']=receivers.name
    if recipe.get('look')=='CAMERA_MATCHED':
        # These emitters fit the part's photographed reflections. Lighting the
        # proxy floor with them adds deep shadows absent from the camera plate.
        # Ambient illumination still supplies the rendered contact shadow.
        for light in scene.objects:
            if 'reflection_bar_index' in light:
                light.light_linking.receiver_collection=receivers
    # Make the housing less white and more like worn, translucent grey plastic.
    for name in ('Brushed frame','Warm diffuser','Diffuser diodes'):
        mat=bpy.data.materials.get(PREFIX+name)
        if mat:
            shader=mat.node_tree.nodes.get('Principled BSDF')
            if name=='Brushed frame':shader.inputs['Base Color'].default_value=(.18,.19,.22,1);shader.inputs['Metallic'].default_value=.15
    scene['assembly_look']=recipe.get('look','REFINED')
    from assembly_environment_detail import refine_fixture_detail
    refine_fixture_detail(scene)
