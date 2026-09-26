"""Raised inspection camera and real, visually verified empty-track plates."""
import math
import hashlib
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PLATES=('20260904_051234_623_cam3936.jpg','20260904_051234_931_cam3936.jpg')
PLATE_DIR=ROOT/'assets'/'assembly_cam3936'
WARM_PLATE=ROOT/'assets'/'assembly_warm_track'/'empty_track.png'
CAMERA_LOOKS=('CAMERA_MATCHED','WARM_TRACK')


def plate_assets(look=None):
    old=tuple('assets/assembly_cam3936/'+n for n in PLATES)+('assets/assembly_cam3936/provenance.json',)
    warm=('assets/assembly_warm_track/empty_track.png','assets/assembly_warm_track/provenance.json')
    return warm if look=='WARM_TRACK' else old if look=='CAMERA_MATCHED' else old+warm


def choose_plate(seed):
    # Do not alternate by seed parity: the dent/fold schedule alternates too.
    value=hashlib.sha256(f'empty-track:{seed}'.encode()).digest()
    return PLATES[int.from_bytes(value[:8],'big')%len(PLATES)]


def track_position(scene,travel):
    """Place the nominal center along the observed diagonal camera corridor.

    This is single-view placement, not measured machine kinematics. Keeping
    the former straight world-Y path would move parts across the foreground
    shield after raising the camera.
    """
    from mathutils import Vector
    from bpy_extras.object_utils import world_to_camera_view
    camera=scene.camera;anchor=Vector((-.8,0,.667))
    p=world_to_camera_view(scene,camera,anchor)
    slope=10.2 if scene.get('assembly_camera_profile')=='WARM_TRACK' else 16.5
    px=p.x*1920+100*travel;py=(1-p.y)*1200+slope*travel
    unit=camera.data.sensor_width/camera.data.lens/1920
    ray=camera.matrix_world.to_quaternion()@Vector(((px-960+camera.data.shift_x*1920)*unit,(600-py+camera.data.shift_y*1920)*unit,-1))
    hit=camera.location+ray*((anchor.z-camera.location.z)/ray.z)
    return hit.x-anchor.x,hit.y-anchor.y


def configure_camera(scene,camera,look='CAMERA_MATCHED'):
    import bpy
    from mathutils import Vector,Quaternion
    from bpy_extras.object_utils import world_to_camera_view
    from pipe_studio import aim
    warm=look=='WARM_TRACK'
    scene['assembly_camera_profile']=look
    camera.location=(3,-40,36) if warm else (8,-40,30);aim(camera,(-.8,0,.667))
    camera.data.lens=63;camera.data.shift_x=0;camera.data.shift_y=0
    bpy.context.view_layer.update()
    a=world_to_camera_view(scene,camera,Vector((-3,0,.667)));b=world_to_camera_view(scene,camera,Vector((3,0,.667)))
    angle=math.atan2(-(b.y-a.y)*1200,(b.x-a.x)*1920)
    roll=math.radians(1.2 if warm else 2.5)-angle
    camera.rotation_euler=(camera.rotation_euler.to_quaternion()@Quaternion((0,0,1),roll)).to_euler()
    bpy.context.view_layer.update()
    # Fit only an invariant nominal exterior; defects must not affect framing.
    knots=((-4.90,.045),(-4.52,.194),(-3.98,.326),(-3.30,.378),(-2.44,.41),(-1.78,.61),(3.19,.62),(3.30,.667),(3.335,.607))
    points=[Vector((x,r*math.cos(j*math.tau/64),.667+r*math.sin(j*math.tau/64))) for x,r in knots for j in range(64)]
    def bounds():
        p=[world_to_camera_view(scene,camera,v) for v in points]
        return min(v.x for v in p)*1920,max(v.x for v in p)*1920,min(1-v.y for v in p)*1200,max(1-v.y for v in p)*1200
    width,cx,cy=(572,560,745) if warm else (550,872,775)
    x0,x1,y0,y1=bounds();camera.data.lens*=width/(x1-x0)
    bpy.context.view_layer.update();x0,x1,y0,y1=bounds()
    camera.data.shift_x=((x0+x1)/2-cx)/1920
    camera.data.shift_y=(cy-(y0+y1)/2)/1920
    bpy.context.view_layer.update()
    scene['assembly_camera_elevation_deg']=math.degrees(math.atan2(camera.location.z-.667,math.hypot(camera.location.x+.8,camera.location.y)))
    scene['assembly_camera_fit']=f'Inferred elevated camera, nominal {width}px assembly width centered at ({cx},{cy}); reference 1920x1200'


def sync_plate_view(scene):
    tree=scene.compositing_node_group
    if tree is None:return
    node=tree.nodes.get('Assembly plate inverse view')
    if node:
        for name in ('view_transform','look'):
            setattr(node.view_settings,name,getattr(scene.view_settings,name))
        node.display_settings.display_device=scene.display_settings.display_device
        tree.nodes['Assembly plate exposure compensation'].inputs['Exposure'].default_value=-scene.view_settings.exposure


def configure_plate(scene,recipe):
    import bpy
    from assembly_scene import PREFIX
    warm=recipe.get('look')=='WARM_TRACK'
    path=WARM_PLATE if warm else PLATE_DIR/choose_plate(recipe['seed'])
    if not path.exists():raise FileNotFoundError('Missing visually verified empty track plate: '+str(path))
    # These fixtures still exist for editing, but the beauty background is the
    # camera plate. Only the real 3D parts and contact shadows are composited.
    for obj in scene.objects:
        if obj.type=='MESH' and 'part_class_id' not in obj:
            obj.hide_render=True
    bed=bpy.data.objects[PREFIX+'Teal bed'];bed.hide_render=False;bed.is_shadow_catcher=True
    # This simplified floor is a contact-shadow proxy. Its opaque blue diffuse
    # reflection produced a green band absent from the photographed brass.
    # Let glossy rays see the warm inferred machine fill instead.
    bed.visible_glossy=False
    # Warm machine fill gives the shaded brass its brown-gold response; keep
    # the floor's actual teal bounce and contact-shadow interaction.
    scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.24,.19,.14,1)
    scene.world.node_tree.nodes['Background'].inputs[1].default_value=.18
    fill=bpy.data.objects[PREFIX+'Ambient fill'];fill.data.color=(1,.84,.66)
    if warm:
        scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.30,.24,.18,1)
        scene.world.node_tree.nodes['Background'].inputs[1].default_value=.25
        fill.data.color=(1,.88,.73)
    scene.render.film_transparent=True
    tree=scene.compositing_node_group;n=tree.nodes;link=tree.links.new
    plate=n.new('CompositorNodeImage');plate.name='Assembly empty camera plate'
    plate.image=bpy.data.images.load(str(path),check_existing=False);plate.image.colorspace_settings.name='Non-Color';plate.image.pack()
    source=plate.outputs['Image']
    plate_w,plate_h=plate.image.size
    if (scene.render.resolution_x,scene.render.resolution_y)!=(plate_w,plate_h):
        scale=n.new('CompositorNodeScale');scale.inputs['Type'].default_value='Relative';scale.inputs['X'].default_value=scene.render.resolution_x/plate_w;scale.inputs['Y'].default_value=scene.render.resolution_y/plate_h
        link(source,scale.inputs['Image']);source=scale.outputs['Image']
    inverse=n.new('CompositorNodeConvertToDisplay');inverse.name='Assembly plate inverse view';inverse.inputs['Invert'].default_value=True
    link(source,inverse.inputs['Image'])
    compensate=n.new('CompositorNodeExposure');compensate.name='Assembly plate exposure compensation';link(inverse.outputs['Image'],compensate.inputs['Image'])
    merge=n.new('CompositorNodeAlphaOver');merge.name='Assembly camera composite'
    link(compensate.outputs['Image'],merge.inputs['Background']);link(n['PS_CR_Highlights'].outputs['Image'],merge.inputs['Foreground'])
    link(merge.outputs['Image'],n['PS_CR_Output'].inputs['Image'])
    scene['assembly_background_source']=str(path)
    scene['assembly_background_mode']='Photographic empty track; rendered assemblies and contact shadows'
    if warm:scene['assembly_background_mode']='AI-edited reference photograph with original assembly removed; rendered assemblies and contact shadows'
    sync_plate_view(scene)
