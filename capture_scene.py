"""Square September inspection fixtures, modelled from the four supplied frames.

All image content is rendered geometry. The photographs are only comparison
references, never backplates, textures or negative training samples.
"""
import math
import bpy
from inspection_scene import _box, _cylinder, _material, _thread

PREFIX = 'PS_Capture_'

def build_capture(collection):
    objects = []
    black = _material('CaptureBlack', (.0006,.0008,.001), .05,.88,.15)
    back = _material('CaptureBack', (.022,.024,.029), .12,.88,.12)
    steel = _material('CaptureSteel', (.24,.27,.31), .83,.38,.13)
    dull = _material('CaptureDull', (.055,.063,.079), .62,.61,.18)
    screw = _material('CaptureScrew', (.075,.093,.095), .78,.37,.13)
    def add(obj, views=('UPRIGHT','FOREGROUND')):
        obj.name = PREFIX + obj.name.removeprefix('PS_EnvMachine_')
        obj['capture_views'] = list(views)
        objects.append(obj)
        return obj
    add(_box(collection,'SquareBacking',(-1,3.2,1),(18,.3,15),back))
    for name,radius,depth,y in [('Wheel',2.85,.5,.5),('WheelRim',2.9,.10,.20),('WheelInset',2.78,.04,.12)]:
        add(_cylinder(collection,name,(-5.22,y,1.55),radius,depth,black,'Y'))
    add(_box(collection,'UprightRail',(-5.10,.9,1),(.15,.2,12),steel))
    add(_cylinder(collection,'LeftColumn',(-5.48,-.25,1),.45,12,dull))
    add(_cylinder(collection,'RightCylinder',(1.82,.3,4.45),.85,5.38,dull))
    add(_cylinder(collection,'RightScrew',(1.82,.3,.89),.30,1.78,screw))
    add(_thread(collection,(1.82,.3,.89),screw,length=1.78,pitch=.10,crest_height=.043))
    add(_cylinder(collection,'LowerRod',(1.82,.3,-.65),.315,1.3,steel))
    jaw=add(_box(collection,'LeftJaw',(-4.1,-.30,-3.08),(4.6,2.2,1.65),steel,.045))
    jaw.rotation_euler.y=math.radians(-14)
    jaw=add(_box(collection,'RightJaw',(2.1,.20,-1.98),(2.55,1.20,1.85),steel,.028))
    jaw.rotation_euler.y=math.radians(-9)
    core=add(_cylinder(collection,'TraverseCore',(-.9,.0,-2.78),.20,3.4,screw,'X'))
    core.rotation_euler.y=math.radians(55)
    helix=add(_thread(collection,(-.9,.0,-2.78),screw,radius=.20,length=3.4,pitch=.13,crest_height=.045))
    helix.rotation_euler.y=math.radians(55)
    rail=add(_box(collection,'BottomRail',(-.8,.4,-3.63),(10,1.2,.21),steel,.025))
    rail.rotation_euler.y=math.radians(-9)
    # A second clean specimen is an unlabelled fixture, as in references 1/2.
    from geometry import PipeSpec, build_mesh
    spec=PipeSpec(length=8,radius=1.02,end_ratio=.70,taper_start=.78,taper_end=.88,defect='NONE')
    vertices,faces,_,regions=build_mesh(spec,axial=100,radial=96)
    mesh=bpy.data.meshes.new(PREFIX+'AdjacentPipeMesh'); mesh.from_pydata(vertices,[],faces); mesh.update()
    obj=bpy.data.objects.new(PREFIX+'AdjacentPipe',mesh); collection.objects.link(obj)
    obj.rotation_euler.y=-math.pi/2; obj.location=(-4.8,-.8,-.01)
    mesh.materials.append(_material('CaptureAdjacentBrass',(.047,.035,.014),.88,.50,.35))
    for polygon,region in zip(mesh.polygons,regions): polygon.use_smooth=region!='rim'
    add(obj,('FOREGROUND',))
    # The inverted view has a different mounting assembly and rear enclosure.
    inv=('INVERTED',)
    add(_box(collection,'InverseBacking',(0,3,0),(15,.3,14),black),inv)
    add(_box(collection,'InverseRearPost',(1.65,2,-.7),(.85,.9,8),back),inv)
    add(_box(collection,'InverseCrossbar',(0,.5,3.6),(8,.8,.58),steel),inv)
    for side in (-1,1):
        add(_box(collection,f'InverseUpper{side}',(side*2.9,-.15,3.3),(2.55,1.25,2.3),dull,.035),inv)
        add(_box(collection,f'InverseLip{side}',(side*2.9,-.65,2.15),(2.7,.25,.10),steel,.016),inv)
        add(_cylinder(collection,f'InverseWheel{side}',(side*5.9,.3,-1.65),3,.48,black,'Y'),inv)
    add(_box(collection,'InverseLeftPost',(-3.85,-.8,0),(.30,.5,12),dull),inv)
    return objects

def configure_capture(scene,p):
    active=p.environment=='MACHINE' and p.capture_view!='ORIGINAL'
    for obj in bpy.data.objects:
        if obj.name.startswith(PREFIX):
            obj.hide_render=not active or p.capture_view not in obj.get('capture_views',[])
            obj.hide_set(obj.hide_render)
    if active:
        # The old brass recipe is visibly too yellow for this camera. These
        # reference-specific reflectance adjustments run after update_brass,
        # so they never accumulate and the original scenes keep their finish.
        nodes=bpy.data.materials['PS_Brass'].node_tree.nodes
        for name in ('AlloyColors','OxideColors'):
            for element in nodes[name].color_ramp.elements:
                r,g,b,a=element.color
                element.color=(r*.74,g*.84,min(1,b*1.85),a)
        for name in ('Fresh metal in drawing marks','Handling smudge color','Dark pinprick color','Handling scuff color'):
            r,g,b,a=nodes[name].inputs[2].default_value
            nodes[name].inputs[2].default_value=(r*.74,g*.84,min(1,b*1.85),a)
        # Broad off-axis reflections give the machined jaws their pale faces.
        jaw_fill=bpy.data.objects.get(PREFIX+'JawReflection')
        if jaw_fill is None:
            from pipe_studio import make_light
            jaw_fill=make_light(bpy.data.collections['PS_Studio'],'Capture_JawReflection',(-4,-2,-2),25,4,3)
            jaw_fill['capture_views']=['UPRIGHT','FOREGROUND','INVERTED']
        jaw_fill.location=(-4,-2,2 if p.capture_view=='INVERTED' else -2)
        from pipe_studio import aim
        aim(jaw_fill,(-4,0,2 if p.capture_view=='INVERTED' else -2))
        jaw_fill.hide_render=False; jaw_fill.hide_set(False)
    if active and p.capture_view=='INVERTED':
        # Reflect source placement about the rig midplane, keeping gravity/camera
        # orientation fixed: the shoulder highlight now comes from below.
        from pipe_studio import aim
        shoulder=-p.length*((p.taper_start+p.taper_end)/2-.5)
        for name in ('Key','Fill','Rim','Bounce'):
            light=bpy.data.objects['PS_'+name]
            light.location.z=-light.location.z
            aim(light,(0,0,shoulder) if name in ('Key','Rim') else (0,0,0))
