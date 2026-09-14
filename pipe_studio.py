"""Pipe Studio: Blender 5.1 tool and isolated background renderer.

Launch: blender --factory-startup --python pipe_studio.py
Worker: blender -b --factory-startup --python pipe_studio.py -- --job job.json
"""
import argparse
from dataclasses import asdict
from datetime import datetime
import json
import math
import os
from pathlib import Path
import random
import subprocess
import sys
import traceback
import uuid

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Vector

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if __name__=='__main__':
    sys.modules['pipe_studio']=sys.modules[__name__]
from geometry import PipeSpec, build_mesh, random_spec, yolo_box
from scene_presets import SCENE_PRESETS, REFERENCE_PATHS
from brass_material import build_brass, update_brass
from camera_response import configure_camera_response, set_diagnostic_mode
from lighting_profiles import LIGHTING_ITEMS, lighting_settings
from brass_finishes import FINISH_ITEMS,finish_settings
from product_modes import PRODUCT_DEFAULTS, initial_settings
from shell_appearance import POLYMER_DEFAULTS

bl_info = {"name": "Tapered Pipe Studio", "author": "Pipe Studio", "version": (1, 0, 0),
           "blender": (5, 1, 0), "location": "3D View > Sidebar > Pipe Studio",
           "description": "Hollow metallic pipe visualization and synthetic surface defects", "category": "3D View"}
PREFIX = "PS_"
SUSPENDED = False
GEOMETRY_DIRTY = False
ACTIVE_JOB = None
SPEC_KEYS = tuple(PipeSpec.__dataclass_fields__)
EXTRA_KEYS = ("roughness", "texture_strength", "key_power", "key_angle", "fill_power", "exposure",
              "background", "camera_yaw", "camera_elevation", "focus_blur", "resolution", "samples",
              "wear", "light_softness", "color_cast", "sensor_noise", "environment", "camera_zoom",
              "camera_shift_x", "camera_shift_y", "frame_aspect", "ambient_strength", "brass_green", "rim_power", "tone_mapping",
              "lighting_profile", "light_azimuth", "key_span", "finish_marks", "oxide_amount", "polish_amount") + tuple(PRODUCT_DEFAULTS)


def settings_dict(p):
    values={key:getattr(p,key) for key in SPEC_KEYS+EXTRA_KEYS}
    return {key:round(value,6) if isinstance(value,float) else value for key,value in values.items()}


def get_spec(p):
    values=settings_dict(p)
    return PipeSpec(**{key:values[key] for key in SPEC_KEYS}).validate()


def apply_settings(scene, values):
    global SUSPENDED
    SUSPENDED = True
    try:
        for key in SPEC_KEYS + EXTRA_KEYS:
            if key in values:
                setattr(scene.pipe_studio, key, values[key])
    finally:
        SUSPENDED = False
    refresh(scene, geometry=True)


def atomic_json(path, data):
    path = Path(path)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2), encoding="utf-8")
    temporary.replace(path)


def aim(obj, point=(0, 0, 0)):
    obj.rotation_euler = (Vector(point) - obj.location).to_track_quat('-Z', 'Y').to_euler()


def save_blend(path):
    # Avoid thumbnail writes outside the project during scripted saves.
    prefs=bpy.context.preferences.filepaths
    previous=prefs.file_preview_type
    try:
        prefs.file_preview_type='NONE'
        bpy.ops.wm.save_as_mainfile(filepath=str(path),check_existing=False)
    finally:
        prefs.file_preview_type=previous


def configure_renderer(scene):
    bpy.context.preferences.use_preferences_save=False
    cache=ROOT/'.cache'/'optix'
    cache.mkdir(parents=True,exist_ok=True)
    os.environ['OPTIX_CACHE_PATH']=str(cache)
    scene.render.engine = 'CYCLES'
    scene.cycles.samples = 32
    scene.cycles.preview_samples = 64
    scene.cycles.use_denoising = True
    scene.cycles.use_preview_denoising = True
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = .012
    scene.cycles.max_bounces = 6
    scene.render.image_settings.file_format = 'PNG'
    scene.render.image_settings.color_mode = 'RGB'
    scene.render.image_settings.color_depth = '8'
    scene.render.film_transparent = False
    scene.render.resolution_percentage = 100
    scene.view_settings.view_transform = 'AgX'
    prefs = bpy.context.preferences.addons['cycles'].preferences
    device = 'CPU'
    for backend in ('OPTIX', 'CUDA', 'HIP', 'METAL'):
        try:
            prefs.compute_device_type = backend
            prefs.refresh_devices()
            available = [d for d in prefs.devices if d.type == backend]
            if available:
                for d in prefs.devices:
                    d.use = d.type == backend
                scene.cycles.device = 'GPU'
                device = available[0].name
                break
        except (TypeError, RuntimeError):
            continue
    scene['pipe_device'] = device


def material(name):
    mat = bpy.data.materials.get(PREFIX+name) or bpy.data.materials.new(PREFIX+name)
    mat.use_nodes = True
    mat.node_tree.nodes.clear()
    return mat


def make_materials():
    mat = material('Brass')
    build_brass(mat)

    mask=material('Mask')
    n, link=mask.node_tree.nodes,mask.node_tree.links.new
    out=n.new('ShaderNodeOutputMaterial'); emission=n.new('ShaderNodeEmission')
    attr=n.new('ShaderNodeAttribute'); attr.attribute_name='defect_mask'
    gate=n.new('ShaderNodeMath'); gate.operation='GREATER_THAN'; gate.inputs[1].default_value=.5
    link(attr.outputs['Fac'],gate.inputs[0]); link(gate.outputs[0],emission.inputs['Color'])
    link(emission.outputs[0],out.inputs['Surface'])

    floor=material('Floor')
    n=floor.node_tree.nodes
    out=n.new('ShaderNodeOutputMaterial'); shader=n.new('ShaderNodeBsdfPrincipled'); shader.name='FloorShader'
    shader.inputs['Roughness'].default_value=.78
    floor.node_tree.links.new(shader.outputs[0],out.inputs[0])
    black=material('Black')
    n=black.node_tree.nodes; out=n.new('ShaderNodeOutputMaterial'); shader=n.new('ShaderNodeEmission')
    shader.inputs['Color'].default_value=(0,0,0,1)
    black.node_tree.links.new(shader.outputs[0],out.inputs[0])


def make_light(collection, name, location, power, width, height):
    data=bpy.data.lights.new(PREFIX+name,'AREA'); data.energy=power
    data.shape='RECTANGLE'; data.size=width; data.size_y=height
    obj=bpy.data.objects.new(PREFIX+name,data); collection.objects.link(obj)
    obj.location=location; aim(obj)
    return obj


def setup_scene(scene):
    # Only rebuild the collection owned by this tool; preserve any other scene objects.
    old=bpy.data.collections.get(PREFIX+'Studio')
    if old:
        for obj in list(old.objects):
            bpy.data.objects.remove(obj,do_unlink=True)
        bpy.data.collections.remove(old)
    collection=bpy.data.collections.new(PREFIX+'Studio'); scene.collection.children.link(collection)
    make_materials()
    mesh=bpy.data.meshes.new(PREFIX+'PipeMesh')
    pipe=bpy.data.objects.new(PREFIX+'Pipe',mesh); collection.objects.link(pipe)
    pipe.data.materials.append(bpy.data.materials[PREFIX+'Brass'])
    lip=pipe.modifiers.new('Cut edge rounding','BEVEL')
    lip.limit_method='ANGLE'; lip.angle_limit=math.radians(55)
    lip.segments=3; lip.width=.004; lip.use_clamp_overlap=True
    floor_mesh=bpy.data.meshes.new(PREFIX+'FloorMesh')
    # A circular studio sweep keeps low-angle shots free of a hard horizon.
    # The camera and lights sit inside the flat central floor and curved wall.
    sweep=[(20+10*math.sin(i*math.pi/24),10*(1-math.cos(i*math.pi/24))) for i in range(13)]
    sweep.append((30,40))
    floor_vertices=[(r*math.cos(j*math.tau/128),r*math.sin(j*math.tau/128),z)
                    for r,z in sweep for j in range(128)]
    floor_faces=[tuple(range(128))]
    for i in range(len(sweep)-1):
        for j in range(128):
            a=i*128+j; b=i*128+(j+1)%128
            floor_faces.append((a,a+128,b+128,b))
    floor_mesh.from_pydata(floor_vertices,[],floor_faces)
    for polygon in floor_mesh.polygons:
        polygon.use_smooth=polygon.index>0
    floor=bpy.data.objects.new(PREFIX+'Floor',floor_mesh); collection.objects.link(floor)
    floor.data.materials.append(bpy.data.materials[PREFIX+'Floor'])
    camera=bpy.data.objects.new(PREFIX+'Camera',bpy.data.cameras.new(PREFIX+'Camera'))
    collection.objects.link(camera); scene.camera=camera
    camera.data.type='PERSP'; camera.data.sensor_width=36; camera.data.dof.focus_object=pipe
    camera.data.passepartout_alpha=.92
    make_light(collection,'Key',(-1,-4,5),650,6,.8)
    make_light(collection,'Fill',(1,3,3),250,5,4)
    make_light(collection,'Rim',(-1,2,4),650,5,.5)
    make_light(collection,'Bounce',(-3,-3,1),5,3,7)
    from inspection_scene import build_machine, build_godslight
    for obj in build_machine(collection)+build_godslight(collection):
        obj['pipe_beauty_materials']=[m.name for m in obj.data.materials] if hasattr(obj.data,'materials') else []
    scene.world=bpy.data.worlds.new(PREFIX+'World')
    scene.world.use_nodes=True
    scene.world.node_tree.nodes['Background'].inputs['Color'].default_value=(.28,.31,.36,1)
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=.30
    configure_renderer(scene)
    refresh(scene,geometry=True)
    bpy.context.view_layer.objects.active=pipe
    for obj in bpy.context.selected_objects:
        obj.select_set(False)
    pipe.select_set(True)


def rebuild_pipe(scene):
    p=scene.pipe_studio; spec=get_spec(p)
    vertices,faces,masks,regions=build_mesh(spec,axial=224 if p.resolution>1200 else 144,
                                          radial=160 if p.resolution>1200 else 128,adaptive=True)
    obj=bpy.data.objects[PREFIX+'Pipe']; old=obj.data
    mesh=bpy.data.meshes.new(PREFIX+'PipeMesh')
    mesh.from_pydata(vertices,[],faces)
    mesh.update()
    attribute=mesh.attributes.new('defect_mask','FLOAT','POINT')
    attribute.data.foreach_set('value',masks)
    # Keep flat annular edges and smooth side walls.
    for poly,region in zip(mesh.polygons,regions):
        poly.use_smooth=region!='rim'
    mesh.materials.append(bpy.data.materials[PREFIX+('Mask' if p.mask_view else 'Brass')])
    obj.data=mesh
    if old.users==0:
        bpy.data.meshes.remove(old)
    scene['pipe_error']=''


def refresh(scene,geometry=False):
    if scene.pipe_studio.product_mode=='FLASHLIGHT':
        import flashlight_integration as flashlight
        flashlight.refresh(scene,settings_dict(scene.pipe_studio))
        flashlight.mask_view(scene,scene.pipe_studio.mask_view)
        return
    from flashlight_integration import activate_pipe
    activate_pipe(scene)
    if PREFIX+'Pipe' not in bpy.data.objects:
        setup_scene(scene)
        return
    p=scene.pipe_studio
    if geometry:
        rebuild_pipe(scene)
    upright=p.environment=='MACHINE'
    pipe=bpy.data.objects[PREFIX+'Pipe']
    pipe.rotation_euler=(0,-math.pi/2 if upright else 0,0)
    lip=pipe.modifiers.get('Cut edge rounding')
    if lip:
        lip.width=p.radius*p.wall_ratio*.12
    cam=bpy.data.objects[PREFIX+'Camera']
    yaw,elevation=math.radians(p.camera_yaw),math.radians(p.camera_elevation)
    distance=60 if upright else 24 if p.environment=='GODSLIGHT' else 12
    target=(0,0,p.length*.12 if upright else 0)
    cam.location=(distance*math.sin(yaw)*math.cos(elevation),-distance*math.cos(yaw)*math.cos(elevation),
                  target[2]+distance*math.sin(elevation))
    aim(cam,target)
    frame_width=(p.length*1.10*p.frame_aspect if upright else max(p.length*1.28,p.radius*5.5))/p.camera_zoom
    cam.data.ortho_scale=frame_width
    cam.data.lens=distance*cam.data.sensor_width/frame_width
    cam.data.clip_end=250
    cam.data.shift_x=p.camera_shift_x; cam.data.shift_y=p.camera_shift_y
    cam.data.dof.use_dof=p.focus_blur>0
    # Focus the photographed front wall, not the empty bore axis behind it.
    from geometry import radius_at
    local_view=pipe.rotation_euler.to_matrix().inverted() @ (cam.location-Vector(target))
    theta=math.atan2(local_view.z,local_view.y)
    focal_radius=radius_at(.5,get_spec(p))
    local_surface=Vector((0,focal_radius*math.cos(theta),focal_radius*math.sin(theta)))
    surface=pipe.rotation_euler.to_matrix() @ local_surface+pipe.location
    forward=(Vector(target)-cam.location).normalized()
    cam.data.dof.focus_object=None
    cam.data.dof.focus_distance=max(.01,(surface-cam.location).dot(forward))
    cam.data.dof.aperture_fstop=(max(.035,8*math.exp(-7*p.focus_blur)) if p.environment=='GODSLIGHT'
                               else max(.35,8.0/(1+p.focus_blur*8)))
    cam.data.dof.aperture_blades=8
    key=bpy.data.objects[PREFIX+'Key']
    shoulder=p.length*((p.taper_start+p.taper_end)/2-.5)
    light_target=(0,0,shoulder) if upright else (shoulder,0,0) if p.environment=='GODSLIGHT' else (0,0,0)
    key_x=-.65 if upright else p.length*.65 if p.environment=='GODSLIGHT' else -p.length*.15
    key.location=(key_x,-4.8*math.cos(math.radians(p.key_angle)),
                  light_target[2]+4.8*math.sin(math.radians(p.key_angle)))
    azimuth=math.radians(p.light_azimuth)
    key.location.x+=4.8*math.sin(azimuth)
    key.location.y*=math.cos(azimuth)
    aim(key,light_target); key.data.energy=p.key_power
    key.data.shape='ELLIPSE' if upright else 'RECTANGLE'
    if upright:
        key.rotation_euler.rotate_axis('Z',math.radians(12))
    key.data.size=(p.radius*10 if upright else p.length)*p.key_span
    key.data.size_y=p.light_softness
    cast=p.color_cast
    key.data.color=(1-.12*cast,1,1-.45*cast) if cast>=0 else (1+.30*cast,1+.10*cast,1)
    fill=bpy.data.objects[PREFIX+'Fill']; fill.data.energy=p.fill_power
    fill.location=(0,-5,1) if upright else (1,-4,2) if p.environment=='GODSLIGHT' else (1,3,3)
    fill.data.size=5; fill.data.size_y=6 if upright else 4; aim(fill)
    rim=bpy.data.objects[PREFIX+'Rim']; rim.data.energy=p.rim_power
    rim.location=(0,1.7,p.length*.5+1.5) if upright else (-1,2,4)
    rim.data.size=3 if upright else 5; rim.data.size_y=.5; aim(rim,light_target)
    # Reference rig tint belongs to the illumination, not the brass alloy.
    # Assign from a fixed base on every refresh so environment changes reset it.
    fill.data.color=rim.data.color=(1,1,1)
    if p.environment=='GODSLIGHT':
        rig_cast=max(0,cast)
        red=1-(.23/.38)*rig_cast; blue=1-(.07/.38)*rig_cast
        key.data.color.r*=red; key.data.color.b*=blue
        fill.data.color=rim.data.color=(red,1,blue)
    bounce=bpy.data.objects.get(PREFIX+'Bounce')
    if bounce:
        bounce.location=(-3,-3,1) if upright else (2,-3,-1)
        bounce.data.energy=p.fill_power*.35 if p.environment!='STUDIO' else 0
        bounce.data.color=(.83,.91,1); aim(bounce)
    update_brass(bpy.data.materials[PREFIX+'Brass'],p)
    floor=bpy.data.objects[PREFIX+'Floor']; floor.location.z=-p.radius*1.02
    floor.hide_render=p.environment!='STUDIO'; floor.hide_set(floor.hide_render)
    for obj in bpy.data.collections[PREFIX+'Studio'].objects:
        if obj.name.startswith('PS_EnvMachine_'):
            obj.hide_render=not upright; obj.hide_set(obj.hide_render)
        elif obj.name.startswith('PS_EnvGods_'):
            obj.hide_render=p.environment!='GODSLIGHT'; obj.hide_set(obj.hide_render)
    colors={'DARK':(.018,.025,.035,1),'GREY':(.19,.22,.25,1),'GREEN':(.075,.10,.035,1)}
    bpy.data.materials[PREFIX+'Floor'].node_tree.nodes['FloorShader'].inputs['Base Color'].default_value=colors[p.background]
    scene.view_settings.exposure=p.exposure
    scene.view_settings.view_transform='Standard' if p.tone_mapping=='STANDARD' else 'AgX'
    scene.render.resolution_x=p.resolution
    scene.render.resolution_y=round(p.resolution/p.frame_aspect)
    scene.cycles.samples=p.samples
    scene.cycles.seed=p.seed
    configure_camera_response(scene,p)
    set_mask_mode(scene,p.mask_view)
    bpy.context.view_layer.update()


def set_mask_mode(scene,enabled):
    set_diagnostic_mode(scene,enabled)
    bpy.data.objects[PREFIX+'Pipe'].data.materials[0]=bpy.data.materials[PREFIX+('Mask' if enabled else 'Brass')]
    bpy.data.objects[PREFIX+'Floor'].data.materials[0]=bpy.data.materials[PREFIX+('Black' if enabled else 'Floor')]
    for obj in bpy.data.collections[PREFIX+'Studio'].objects:
        if obj.name.startswith(('PS_EnvMachine_','PS_EnvGods_')) and hasattr(obj.data,'materials'):
            originals=obj.get('pipe_beauty_materials',[])
            for index,name in enumerate(originals):
                obj.data.materials[index]=bpy.data.materials[PREFIX+'Black'] if enabled else bpy.data.materials[name]
    scene.world.node_tree.nodes['Background'].inputs['Strength'].default_value=0 if enabled else scene.pipe_studio.ambient_strength


def delayed_refresh():
    global GEOMETRY_DIRTY
    scene=bpy.context.scene
    geometry=GEOMETRY_DIRTY; GEOMETRY_DIRTY=False
    try:
        refresh(scene,geometry=geometry)
        if 'pipe_error' in scene:
            del scene['pipe_error']
    except Exception as exc:
        scene['pipe_error']=str(exc)
    return None


def on_geometry(self,context):
    global GEOMETRY_DIRTY
    if SUSPENDED or context is None:
        return
    if self.product_mode=='FLASHLIGHT' and self.flashlight_index>=self.flashlight_count:
        self.flashlight_index=self.flashlight_count-1
    GEOMETRY_DIRTY=True
    if not bpy.app.timers.is_registered(delayed_refresh):
        bpy.app.timers.register(delayed_refresh,first_interval=.16)


def on_appearance(self,context):
    if SUSPENDED or context is None:
        return
    if not bpy.app.timers.is_registered(delayed_refresh):
        bpy.app.timers.register(delayed_refresh,first_interval=.08)


def on_lighting_profile(self,context):
    if not SUSPENDED and context is not None:
        if self.product_mode=='FLASHLIGHT':
            on_appearance(self,context)
            return
        apply_settings(context.scene,lighting_settings(self.environment,self.lighting_profile))


def on_product_mode(self,context):
    if SUSPENDED or context is None:
        return
    from app_model import DEFAULTS
    target=self.product_mode
    previous=context.scene.get('_active_product','PIPE')
    snapshot=settings_dict(self)
    snapshot['product_mode']=previous
    context.scene['inspection_settings_'+previous]=json.dumps(snapshot)
    saved=context.scene.get('inspection_settings_'+target)
    values=json.loads(saved) if saved else initial_settings(target,DEFAULTS)
    self.mask_view=False
    apply_settings(context.scene,values)


class PIPE_OT_condition(bpy.types.Operator):
    bl_idname='pipe.condition'; bl_label='Set surface condition'; bl_options={'REGISTER','UNDO'}
    kind: StringProperty(default='DENT')
    def execute(self,context):
        changes={'defect':self.kind}
        if self.kind=='SHALLOW_DENT':
            changes.update(defect='DENT',depth=.015,width=.12,arc=35.,defect_style='DEFAULT')
        if self.kind=='TWIST':changes['flashlight_region']='BODY'
        if self.kind=='SCRATCH':
            changes['flashlight_surface']='METAL'
        if self.kind in ('OPEN_CENTER','PROTRUDING_CRIMP'):
            changes['flashlight_region']='PLASTIC_FACE'
        apply_settings(context.scene,changes)
        return {'FINISHED'}


def visible_angle(scene):
    if scene.pipe_studio.product_mode=='FLASHLIGHT':
        return (90+scene.pipe_studio.flashlight_roll)%360
    cam=bpy.data.objects[PREFIX+'Camera']
    local=bpy.data.objects[PREFIX+'Pipe'].matrix_world.inverted() @ cam.location
    return math.degrees(math.atan2(local.z,local.y))%360


def export_frame(scene,folder,stem):
    """Render beauty and a separately visible surface support mask, then derive its box."""
    if scene.pipe_studio.product_mode=='FLASHLIGHT':
        from flashlight_integration import export_frame as export_flashlight
        return export_flashlight(scene,folder,stem,settings_dict(scene.pipe_studio))
    import numpy as np
    folder=Path(folder)
    for sub in ('images','masks','labels','metadata'):
        (folder/sub).mkdir(parents=True,exist_ok=True)
    p=scene.pipe_studio
    image_path=folder/'images'/(stem+'.png')
    mask_path=folder/'masks'/(stem+'.png')
    state=(scene.view_settings.view_transform,scene.view_settings.exposure,scene.cycles.samples,
           scene.cycles.use_denoising,scene.camera.data.dof.use_dof,scene.render.filepath)
    try:
        refresh(scene)
        set_mask_mode(scene,False)
        scene.render.filepath=str(image_path)
        bpy.ops.render.render(write_still=True)
        if p.sensor_noise>0:
            # Approximate signal-dependent camera noise in linear image values.
            noisy=bpy.data.images.load(str(image_path),check_existing=False)
            try:
                array=np.empty(len(noisy.pixels),dtype=np.float32)
                noisy.pixels.foreach_get(array)
                array=array.reshape(-1,4)
                rng=np.random.default_rng(p.seed)
                sigma=p.sensor_noise*np.sqrt(np.maximum(array[:,:3],0)+.01)
                array[:,:3]=np.clip(array[:,:3]+rng.normal(0,1,array[:,:3].shape)*sigma,0,1)
                noisy.pixels.foreach_set(array.ravel())
                noisy.filepath_raw=str(image_path); noisy.file_format='PNG'; noisy.save()
            finally:
                bpy.data.images.remove(noisy)
        set_mask_mode(scene,True)
        scene.view_settings.view_transform='Standard'
        scene.view_settings.exposure=0
        scene.cycles.samples=4
        scene.cycles.use_denoising=False
        scene.camera.data.dof.use_dof=False
        scene.render.filepath=str(mask_path)
        bpy.ops.render.render(write_still=True)
        im=bpy.data.images.load(str(mask_path),check_existing=False)
        try:
            w,h=im.size
            pixels=np.empty(w*h*4,dtype=np.float32)
            im.pixels.foreach_get(pixels)
            mask=pixels.reshape(h,w,4)[::-1,:,0]>.5
            ys,xs=np.where(mask)
            bbox=None if len(xs)==0 else (int(xs.min()),int(ys.min()),int(xs.max()-xs.min()+1),int(ys.max()-ys.min()+1))
            visible_pixels=int(mask.sum())
            # Store the same crisp binary support used to derive YOLO boxes.
            rgba=np.ones((h,w,4),dtype=np.float32)
            rgba[:,:,:3]=mask[::-1,:,None]
            im.pixels.foreach_set(rgba.ravel())
            im.filepath_raw=str(mask_path); im.file_format='PNG'; im.save()
        finally:
            bpy.data.images.remove(im)
        label=''
        class_id={'FOLD':0,'DENT':1}.get(p.defect)
        if bbox and class_id is not None:
            label=str(class_id)+' '+' '.join(f'{v:.8f}' for v in yolo_box(bbox,w,h))+'\n'
        (folder/'labels'/(stem+'.txt')).write_text(label,encoding='utf-8')
        info={'image':'images/'+stem+'.png','mask':'masks/'+stem+'.png','width':w,'height':h,
              'class_id':class_id,'defect_type':p.defect,'bbox_xywh':bbox,'visible_mask_pixels':visible_pixels,
              'has_visible_geometric_mask':bool(bbox),'parameters':settings_dict(p),
              'mask_definition':'Visible exterior surface where absolute procedural radial displacement is at least 3% of its nominal peak. Crisp geometry support; not perceptual visibility or an acceptance criterion.',
              'calibrated':False,'renderer':'Blender '+bpy.app.version_string+' / Cycles',
              'render_device':scene.get('pipe_device','unknown'),
              'reference_image':REFERENCE_PATHS.get(p.environment),
              'appearance_version':4,'brass_material_version':bpy.data.materials[PREFIX+'Brass'].get('pipe_brass_version'),
              'focus_distance_scene_units':scene.camera.data.dof.focus_distance,
              'mesh_vertices':len(bpy.data.objects[PREFIX+'Pipe'].data.vertices),'adaptive_defect_sampling':True,
              'camera_response':scene.get('pipe_camera_response_status'),
              'environment_note':'Procedural 3D environment and manual visual match; no calibrated camera or measured material data.'}
        atomic_json(folder/'metadata'/(stem+'.json'),info)
        return info
    finally:
        (scene.view_settings.view_transform,scene.view_settings.exposure,scene.cycles.samples,
         scene.cycles.use_denoising,scene.camera.data.dof.use_dof,scene.render.filepath)=state
        set_mask_mode(scene,p.mask_view)


def run_job(job_path):
    job_path=Path(job_path).resolve(); job=json.loads(job_path.read_text(encoding='utf-8'))
    if job['settings'].get('product_mode')=='FLASHLIGHT':
        from flashlight_integration import run_job as run_flashlights
        return run_flashlights(job_path)
    folder=job_path.parent; status_path=folder/'status.json'
    scene=bpy.context.scene
    completed=[]
    try:
        setup_scene(scene)
        base=job['settings']; count=job['count']; seed=base['seed']
        apply_settings(scene,base)
        angle=visible_angle(scene)
        for i in range(count):
            if (folder/'cancel.flag').exists():
                atomic_json(status_path,{'state':'cancelled','completed':len(completed),'total':count,
                                         'last_image':str(folder/completed[-1]['image']) if completed else None})
                break
            current=dict(base)
            if job.get('randomize'):
                rng=random.Random(seed+i*7919)
                spec=random_spec(PipeSpec(**{k:base[k] for k in SPEC_KEYS}),seed+i,
                                 angle if job.get('front_only',True) else None)
                if rng.random()<job.get('clean_fraction',.2):
                    spec.defect='NONE'
                current.update(asdict(spec))
                current.update(roughness=max(.08,min(.75,base['roughness']+rng.uniform(-.06,.06))),
                               key_power=max(50,base['key_power']*rng.uniform(.75,1.25)),
                               key_angle=max(5,min(175,base['key_angle']+rng.uniform(-12,12))),
                               exposure=max(-3,min(3,base['exposure']+rng.uniform(-.25,.25))))
            apply_settings(scene,current)
            atomic_json(status_path,{'state':'rendering','completed':len(completed),'total':count,
                                     'current':i+1,'last_image':str(folder/completed[-1]['image']) if completed else None})
            info=export_frame(scene,folder,f'pipe_{i:05d}')
            completed.append(info)
            atomic_json(folder/'manifest.json',{'classes':{'0':'Fold','1':'Dent'},'samples':completed,
                                              'seed':seed,'calibrated':False})
        else:
            atomic_json(status_path,{'state':'complete','completed':len(completed),'total':count,
                                     'last_image':str(folder/completed[-1]['image']) if completed else None})
        (folder/'classes.txt').write_text('Fold\nDent\n',encoding='utf-8')
        save_blend(folder/'last_scene.blend')
    except Exception:
        atomic_json(status_path,{'state':'failed','completed':len(completed),'error':traceback.format_exc()})
        raise


def launch_job(scene,randomize):
    global ACTIVE_JOB
    p=scene.pipe_studio
    if p.product_mode=='FLASHLIGHT':
        from app_model import validate_settings
        validate_settings(settings_dict(p))
    else:
        get_spec(p)
    if ACTIVE_JOB and ACTIVE_JOB['process'].poll() is None:
        raise RuntimeError('An export is already running. Cancel it or wait for completion.')
    root=Path(bpy.path.abspath(p.output_dir)).expanduser()
    folder=root/(datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:6])
    folder.mkdir(parents=True,exist_ok=False)
    job={'settings':settings_dict(p),'count':p.batch_count if randomize else 1,
         'randomize':randomize,'clean_fraction':p.clean_fraction,'front_only':p.front_only}
    if not randomize and p.product_mode=='FLASHLIGHT' and p.environment=='BUTTON_TRACK':
        job['flashlight_recipe']=json.loads(scene['flashlight_recipe'])
    atomic_json(folder/'job.json',job)
    atomic_json(folder/'status.json',{'state':'starting','completed':0,'total':job['count']})
    with (folder/'render.log').open('w',encoding='utf-8') as log:
        proc=subprocess.Popen([bpy.app.binary_path,'--background','--factory-startup','--python-exit-code','1',
                               '--python',str(ROOT/'pipe_studio.py'),'--','--job',str(folder/'job.json')],
                              stdout=log,stderr=subprocess.STDOUT,cwd=str(ROOT),
                              creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    ACTIVE_JOB={'process':proc,'folder':folder}
    p.last_export=str(folder)
    if not bpy.app.timers.is_registered(poll_job):
        bpy.app.timers.register(poll_job,first_interval=1.0)
    return folder


def read_status(folder):
    try:
        return json.loads((Path(folder)/'status.json').read_text(encoding='utf-8'))
    except (OSError,ValueError):
        return {}


def poll_job():
    if not ACTIVE_JOB:
        return None
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type=='VIEW_3D':
                area.tag_redraw()
    if ACTIVE_JOB['process'].poll() is not None:
        status=read_status(ACTIVE_JOB['folder'])
        if status.get('state') not in ('complete','failed','cancelled'):
            atomic_json(ACTIVE_JOB['folder']/'status.json',{'state':'failed','error':'Renderer exited unexpectedly. See render.log.'})
        return None
    return 1.0


class PIPE_Settings(bpy.types.PropertyGroup):
    flashlight_variation: EnumProperty(name='Capture variation',items=[('VARIED','Varied inspection conditions','Seeded shape, severity, finish, pose, light and sensor variation'),('REFERENCE','Reference conditions','Keep materials, pose and lighting fixed; vary defect identity')],default='VARIED')
    flashlight_crops: EnumProperty(name='Automatic crops',items=[('ON','Flashlights + regions','Also save cropped full flashlights and usable region images'),('OFF','Full camera frames only','Save camera images and labels without crops')],default='ON')
    flashlight_region: EnumProperty(name='Defect region',items=[('TOP','top — brass collar','Curved brass side'),('BODY','body','Long plastic body'),('BRASS_FACE','Brass Face','Brass end face including center button'),('PLASTIC_FACE','Plastic Face','Molded all-plastic end face')],default='BODY',update=on_geometry)
    flashlight_camera: EnumProperty(name='Preview camera',items=[('FRONT_45','Front 45°','Looking along the row from the front end'),('REAR_45','Rear 45°','Opposite end at 45 degrees'),('OVERHEAD','Straight down','Top inspection view'),('REFERENCE','Reference comparison','Estimated photo angle; export with Current camera')],default='FRONT_45',update=on_appearance)
    flashlight_length_scale: FloatProperty(name='Shell length scale',description='Exterior proportions; retains the current defect recipe',default=1.,min=.75,max=1.5,update=on_appearance)
    flashlight_reference_elevation: FloatProperty(name='Reference view elevation',description='Estimated angle for the separate photo-comparison camera',default=55.,min=35,max=70,update=on_appearance)
    flashlight_projection: EnumProperty(name='Oblique projection',items=[('PERSP','Inspection perspective','Natural near/far magnification at 45 degrees'),('ORTHO','Orthographic','Constant magnification across the row')],default='PERSP',update=on_appearance)
    flashlight_capture: EnumProperty(name='Export cameras',items=[('ALL','All three cameras','Same specimen from both 45-degree cameras and overhead'),('CURRENT','Current camera','Only the selected camera')],default='ALL')
    product_mode: EnumProperty(name='Product',items=[('PIPE','Tapered pipe','Hollow brass pipe'),('FLASHLIGHT','Flashlight','Plastic and metal flashlight row')],default='PIPE',update=on_product_mode)
    flashlight_surface: EnumProperty(name='Affected housing',items=[('PLASTIC','Plastic','Plastic body dent'),('METAL','Metal','Bulb housing dent or scratch')],default='PLASTIC',update=on_geometry)
    flashlight_layout: EnumProperty(name='Defect arrangement',items=[('SINGLE','Selected flashlight','Apply defect to one row item'),('MIXED','Mixed row','Clean parts, plastic dents, metal dents and scratches; common severity and footprint')],default='SINGLE',update=on_geometry)
    flashlight_count: IntProperty(name='Flashlights in row',default=6,min=2,max=12,update=on_geometry)
    flashlight_index: IntProperty(name='Selected flashlight (0 = left)',default=2,min=0,max=11,update=on_geometry)
    flashlight_roll: FloatProperty(name='Axial roll (degrees)',default=0,min=-180,max=180,update=on_geometry)
    battery_probability: FloatProperty(name='Battery presence probability',default=.75,min=0,max=1,subtype='FACTOR',update=on_geometry)
    length: FloatProperty(name='Length',default=6,min=2,max=12,update=on_geometry)
    radius: FloatProperty(name='Large radius',default=.72,min=.3,max=1.5,update=on_geometry)
    end_ratio: FloatProperty(name='Outlet / inlet radius',default=.66,min=.35,max=1,update=on_geometry)
    wall_ratio: FloatProperty(name='Wall / inlet radius',default=.10,min=.03,max=.22,update=on_geometry)
    taper_start: FloatProperty(name='Taper start',default=.48,min=0,max=.90,update=on_geometry)
    taper_end: FloatProperty(name='Taper end',default=.88,min=.1,max=1,update=on_geometry)
    body_taper: FloatProperty(name='Body taper',default=0,min=0,max=.12,subtype='FACTOR',update=on_geometry)
    shoulder_roundness: FloatProperty(name='Shoulder rounding',default=1,min=0,max=1,subtype='FACTOR',update=on_geometry)
    crimp_twist: FloatProperty(name='Closure twist (degrees)',default=18,min=0,max=40,update=on_geometry)
    crimp_tightness: FloatProperty(name='Crimp tightness',description='Compact the six folded shoulders and sharpen their seams inside the rolled margin',default=.85,min=0,max=1,update=on_geometry)
    dust_amount: FloatProperty(name='Dust and debris',description='Normal surface appearance; never a defect label. Zero disables it.',default=.22,min=0,max=1,update=on_appearance)
    plastic_roughness: FloatProperty(name='Plastic roughness',description='Higher values soften plastic reflections independently of brass',default=POLYMER_DEFAULTS['plastic_roughness'],min=.12,max=.7,update=on_appearance)
    plastic_specular: FloatProperty(name='Plastic reflection strength',description='Strength of the polymer surface reflection',default=POLYMER_DEFAULTS['plastic_specular'],min=0,max=.6,update=on_appearance)
    plastic_coat: FloatProperty(name='Plastic clear coat',description='Extra glossy reflection; the reference uses almost none',default=POLYMER_DEFAULTS['plastic_coat'],min=0,max=.3,update=on_appearance)
    plastic_finish_variation: FloatProperty(name='Uneven plastic finish',description='Subtle dull and polished patches attached to each shell; not defects',default=POLYMER_DEFAULTS['plastic_finish_variation'],min=0,max=1,update=on_appearance)
    groove_polish: FloatProperty(name='Groove highlight polish',description='Smoothness of rib crests; lower values reduce continuous white stripes',default=POLYMER_DEFAULTS['groove_polish'],min=0,max=1,update=on_appearance)
    groove_residue: FloatProperty(name='Pale groove residue',description='Sparse interrupted residue in grooves; excluded from defect labels',default=POLYMER_DEFAULTS['groove_residue'],min=0,max=1,update=on_appearance)
    crimp_roughness: FloatProperty(name='Crimp roughness',description='Finish of folded plastic, independent of the body',default=POLYMER_DEFAULTS['crimp_roughness'],min=.12,max=.7,update=on_appearance)
    plastic_ink_wear: FloatProperty(name='Body ink wear',description='Uneven and faded body printing; zero is a fresh print',default=POLYMER_DEFAULTS['plastic_ink_wear'],min=0,max=1,update=on_appearance)
    inspection_softness: FloatProperty(name='Optical softness (px)',description='Approximate blur sigma at 1200px image width; zero disables; masks stay sharp',default=POLYMER_DEFAULTS['inspection_softness'],min=0,max=1.5,update=on_appearance)
    inspection_scatter: FloatProperty(name='Highlight scatter',description='Restrained glow around bright reflections; zero disables; beauty only',default=.065,min=0,max=.2,update=on_appearance)
    inspection_light_rig: EnumProperty(name='Inspection bars',items=[('SEGMENTED','Segmented bars','Earlier multi-bar lighting'),('CONTINUOUS','Continuous strip','Wide transverse lamps for more even row coverage')],default='SEGMENTED',update=on_appearance)
    inspection_light_distance: FloatProperty(name='Fixture distance scale',description='Move the inspection lights closer or farther, scaling source size and power with distance',default=1.,min=.45,max=1.6,update=on_appearance)
    inspection_track_finish: EnumProperty(name='Track reflection surface',items=[('DARK','Dark track','Black reflective inspection track'),('METAL','Polished metal','Earlier brass-colored reflection apron')],default='METAL',update=on_appearance)
    crimp_fold_depth: FloatProperty(name='Fold depth',default=.085,min=.035,max=.14,precision=3,update=on_geometry)
    crimp_opening: FloatProperty(name='Opening / face radius',default=.15,min=.005,max=.35,precision=3,update=on_geometry)
    crimp_lift: FloatProperty(name='Center height above rim',default=.08,min=.005,max=.25,precision=3,update=on_geometry)
    crimp_spread: FloatProperty(name='Raised area radius',default=.26,min=.1,max=.42,precision=3,update=on_geometry)
    body_twist: FloatProperty(name='Body twist (degrees)',default=25,min=-140,max=140,description='Signed end-to-end plastic torsion; zero is undeformed',update=on_geometry)
    body_twist_span: FloatProperty(name='Twisted body fraction',default=.65,min=.2,max=.9,update=on_geometry)
    defect: EnumProperty(name='Defect',items=[('NONE','Clean','Undeformed product'),('DENT','Dent','Rounded indentation'),
                         ('FOLD','Fold','Localized crease and raised lip'),('SCRATCH','Scratch','Flashlight grooves'),
                         ('OPEN_CENTER','Open center','Incomplete plastic crimp closure'),('PROTRUDING_CRIMP','Protruding crimp','Folded center pushed beyond the rim'),('TWIST','Body twist','Plastic torsion and buckling')],default='DENT',update=on_geometry)
    defect_style: EnumProperty(name='Defect shape',items=[('DEFAULT','Single','Single localized depression or crease'),
        ('ELONGATED','Elongated','Long trough or crease'),('DOUBLE','Overlapping pair','Two interacting deformations'),
        ('OBLIQUE','Oblique','Tilted asymmetric lip'),('WRINKLED','Wrinkled','Nested deformations'),
        ('BRANCHED','Converging','Converging crease cluster')],default='DEFAULT',update=on_geometry)
    defect_rotation: FloatProperty(name='Defect tilt (deg)',default=0,min=-75,max=75,update=on_geometry)
    secondary_strength: FloatProperty(name='Secondary lobe',default=.5,min=0,max=1,update=on_geometry)
    position: FloatProperty(name='Along pipe',description='Fraction along the pipe, from inlet to outlet',
                            default=.60,min=.03,max=.97,update=on_geometry)
    angle: FloatProperty(name='Around pipe (deg)',default=155,min=0,max=360,update=on_geometry)
    depth: FloatProperty(name='Depth / local radius',default=.13,min=0,max=.25,precision=3,update=on_geometry)
    width: FloatProperty(name='Length / pipe length',default=.075,min=.01,max=.18,precision=3,update=on_geometry)
    arc: FloatProperty(name='Arc width (deg)',default=25,min=8,max=65,update=on_geometry)
    irregularity: FloatProperty(name='Irregularity',default=.24,min=0,max=.65,update=on_geometry)
    seed: IntProperty(name='Seed',default=42,min=0,max=2000000000,update=on_geometry)
    roughness: FloatProperty(name='Roughness',default=.30,min=.06,max=.85,update=on_appearance)
    wear: FloatProperty(name='Surface variation',default=.18,min=0,max=1,update=on_appearance)
    finish_marks: FloatProperty(name='Scuffs and finish marks',default=0,min=0,max=1,update=on_appearance,
                               description='Appearance only; these marks are not labeled as geometric defects')
    oxide_amount: FloatProperty(name='Mottled oxide finish',default=.38,min=0,max=1,update=on_appearance,
                               description='Dull patches interspersed with exposed brass; appearance only')
    polish_amount: FloatProperty(name='Burnished drawing streaks',default=.42,min=0,max=1,update=on_appearance,
                                description='Brighter, sharper reflections on interrupted axial tracks')
    lighting_profile: EnumProperty(name='Lighting option',items=LIGHTING_ITEMS,default='REFERENCE',update=on_lighting_profile)
    light_azimuth: FloatProperty(name='Light side angle (deg)',default=0,min=-80,max=80,update=on_appearance)
    key_span: FloatProperty(name='Light length scale',default=1,min=.25,max=2,update=on_appearance)
    light_softness: FloatProperty(name='Light width',default=1.5,min=.15,max=5,update=on_appearance)
    color_cast: FloatProperty(name='Light tint',default=0,min=-1,max=1,update=on_appearance)
    sensor_noise: FloatProperty(name='Camera noise',default=0,min=0,max=.025,precision=4,update=on_appearance)
    environment: EnumProperty(name='Environment',items=[('STUDIO','Studio','Seamless studio'),
        ('MACHINE','Upright machine','Close inspection scene from supplied screenshot'),
        ('GODSLIGHT','GodsLight horizontal','Horizontal mounted pipe against blurred green machinery'),
        ('TRACK','Flashlight track','Overhead tightly packed row'),('TRACK_GRAZING','Track with grazing inspection','Low side light reveals surface damage'),('BUTTON_TRACK','Brass button track','Exterior reference with three cameras and region labels')],default='STUDIO',update=on_appearance)
    camera_zoom: FloatProperty(name='Framing zoom',default=1,min=.6,max=2.5,update=on_appearance)
    camera_shift_x: FloatProperty(name='Horizontal framing',default=0,min=-.5,max=.5,update=on_appearance)
    camera_shift_y: FloatProperty(name='Vertical framing',default=0,min=-.5,max=.5,update=on_appearance)
    frame_aspect: FloatProperty(name='Frame width / height',default=1.6,min=.8,max=2,update=on_appearance)
    ambient_strength: FloatProperty(name='Ambient light',default=.3,min=0,max=2,update=on_appearance)
    brass_green: FloatProperty(name='Olive brass tint',default=0,min=0,max=1,update=on_appearance)
    rim_power: FloatProperty(name='Rim light',default=455,min=0,max=2500,update=on_appearance)
    tone_mapping: EnumProperty(name='Highlight response',items=[('AGX','Soft studio','Compress bright highlights'),
        ('STANDARD','Inspection clipping','Direct display response with clipped bright reflections')],default='AGX',update=on_appearance)
    texture_strength: FloatProperty(name='Surface grain',default=.16,min=0,max=.7,update=on_appearance)
    key_power: FloatProperty(name='Key light (W)',default=650,min=30,max=2500,update=on_appearance)
    key_angle: FloatProperty(name='Light angle (deg)',default=55,min=5,max=175,update=on_appearance)
    fill_power: FloatProperty(name='Fill light (W)',default=250,min=0,max=1500,update=on_appearance)
    exposure: FloatProperty(name='Exposure (stops)',default=0,min=-3,max=3,update=on_appearance)
    background: EnumProperty(name='Backdrop',items=[('GREY','Studio grey','Neutral backdrop'),
                            ('DARK','Dark','Dark backdrop'),('GREEN','Inspection green','Green backdrop approximation')],
                             default='GREY',update=on_appearance)
    camera_yaw: FloatProperty(name='Orbit (deg)',default=22,min=-175,max=175,update=on_appearance)
    camera_elevation: FloatProperty(name='Elevation (deg)',default=16,min=0,max=70,update=on_appearance)
    focus_blur: FloatProperty(name='Focus blur',default=0,min=0,max=1,update=on_appearance)
    resolution: IntProperty(name='Image width (px)',default=1280,min=320,max=2560,step=160,update=on_appearance)
    samples: IntProperty(name='Render samples',default=48,min=8,max=256,update=on_appearance)
    mask_view: BoolProperty(name='Show affected surface',default=False,update=on_appearance,
                           description='White marks the visible geometric support of the defect; not a visibility score')
    output_dir: StringProperty(name='Output folder',subtype='DIR_PATH',default=str(ROOT/'exports')+os.sep)
    batch_count: IntProperty(name='Number of images',default=12,min=1,max=1000)
    clean_fraction: FloatProperty(name='Clean probability',default=.20,min=0,max=1,
                                 description='Independent probability per image; does not enforce an exact class balance')
    front_only: BoolProperty(name='Keep defects near camera',default=True,
                            description='Sample near the camera-facing surface; visibility is still measured from the mask')
    last_export: StringProperty(name='Last export',default='')
    test_specimens: IntProperty(name='Specimens per environment',default=8,min=3,max=200)
    test_environments: EnumProperty(name='Test environments',items=[('BOTH','Both reference rigs',''),
        ('MACHINE','Upright machine',''),('GODSLIGHT','GodsLight','')],default='BOTH')
    test_quality: EnumProperty(name='Test quality',items=[('QUICK','Quick / 960 px','48 Cycles samples'),
        ('FULL','Reference resolution','Reference-sized images with 192 samples')],default='QUICK')


class PIPE_OT_environment(bpy.types.Operator):
    bl_idname='pipe.environment'; bl_label='Load reference scene'; bl_options={'REGISTER','UNDO'}
    preset: EnumProperty(items=[('MACHINE','Upright photo',''),('GODSLIGHT','GodsLight',''),('STUDIO','Studio',''),('TRACK','Overhead track',''),('TRACK_GRAZING','Grazing track',''),('BUTTON_TRACK','Brass button track','')])
    def execute(self,context):
        if self.preset in ('TRACK','TRACK_GRAZING','BUTTON_TRACK'):
            from product_modes import FLASHLIGHT_PRESETS
            values=FLASHLIGHT_PRESETS[{'TRACK':'Overhead inspection','TRACK_GRAZING':'Grazing inspection','BUTTON_TRACK':'Brass button track'}[self.preset]]
        else:
            values=SCENE_PRESETS[self.preset]
        apply_settings(context.scene,values)
        arrange_view()
        return {'FINISHED'}


class PIPE_OT_brass_finish(bpy.types.Operator):
    bl_idname='pipe.brass_finish'; bl_label='Apply brass finish'; bl_options={'REGISTER','UNDO'}
    preset: EnumProperty(items=FINISH_ITEMS,default='REFERENCE')
    def execute(self,context):
        apply_settings(context.scene,finish_settings(context.scene.pipe_studio.environment,self.preset))
        return {'FINISHED'}


class PIPE_OT_shell_appearance(bpy.types.Operator):
    bl_idname='pipe.shell_appearance'; bl_label='Apply shell appearance'; bl_options={'REGISTER','UNDO'}
    bl_description='Change finish and camera response while preserving the row and its defects'
    preset: EnumProperty(items=[('REFERENCE','Reference finish','Sharper polymer reflections with restrained handling detail'),('CLEAN','Clean finish','Cleaner surfaces and clear camera response; retains defects'),('SATIN','Previous satin','Restore the softer low-reflection finish')])
    @classmethod
    def poll(cls,context):
        p=context.scene.pipe_studio
        return p.product_mode=='FLASHLIGHT' and p.environment=='BUTTON_TRACK'
    def execute(self,context):
        from shell_appearance import appearance_settings
        apply_settings(context.scene,appearance_settings(self.preset))
        return {'FINISHED'}


class PIPE_OT_shell_lighting(bpy.types.Operator):
    bl_idname='pipe.shell_lighting'; bl_label='Apply shell lighting'; bl_options={'REGISTER','UNDO'}
    bl_description='Change inspection lights and track finish while preserving all shells and defects'
    preset: EnumProperty(items=[('PHOTO','Photo lighting','Continuous transverse light with bright upper-body reflections'),('EARLIER','Earlier lighting','Restore the segmented inspection bars and metal apron')])
    @classmethod
    def poll(cls,context):return PIPE_OT_shell_appearance.poll(context)
    def execute(self,context):
        from shell_lighting import LIGHT_PRESETS
        apply_settings(context.scene,LIGHT_PRESETS[self.preset])
        return {'FINISHED'}


class PIPE_OT_reference(bpy.types.Operator):
    bl_idname='pipe.reference'; bl_label='Compare reference in Blender'
    def execute(self,context):
        relative=REFERENCE_PATHS.get(context.scene.pipe_studio.environment)
        if not relative or not (ROOT/relative).exists():
            self.report({'INFO'},'Choose an inspection scene to view its reference.'); return {'CANCELLED'}
        area=next((a for a in context.screen.areas if a.type=='IMAGE_EDITOR'),None)
        if area is None:
            previous={a.as_pointer() for a in context.screen.areas}
            bpy.ops.screen.area_split(direction='VERTICAL',factor=.70)
            area=next((a for a in context.screen.areas if a.as_pointer() not in previous),None)
        if area is None:
            self.report({'WARNING'},'Could not create reference pane.'); return {'CANCELLED'}
        area.type='IMAGE_EDITOR'
        area.spaces.active.image=bpy.data.images.load(str(ROOT/relative),check_existing=True)
        region=next((r for r in area.regions if r.type=='WINDOW'),None)
        if region:
            with context.temp_override(area=area,region=region):
                bpy.ops.image.view_all(fit_view=True)
        return {'FINISHED'}


class PIPE_OT_randomize(bpy.types.Operator):
    bl_idname='pipe.randomize'; bl_label='New defect'; bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        try:
            p=context.scene.pipe_studio
            if p.product_mode=='FLASHLIGHT':
                if p.environment=='BUTTON_TRACK':
                    import button_row
                    index=button_row.mutate(context.scene,settings_dict(p))
                    self.report({'INFO'},f'Updated shell {index+1} of {p.flashlight_count}')
                    return {'FINISHED'}
                apply_settings(context.scene,{'seed':p.seed+1})
                return {'FINISHED'}
            spec=random_spec(get_spec(p),p.seed+1,visible_angle(context.scene))
            apply_settings(context.scene,asdict(spec))
        except Exception as exc:
            self.report({'ERROR'},str(exc)); return {'CANCELLED'}
        return {'FINISHED'}


class PIPE_OT_front(bpy.types.Operator):
    bl_idname='pipe.front'; bl_label='Bring defect to front'; bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        context.scene.pipe_studio.angle=visible_angle(context.scene)
        return {'FINISHED'}


class PIPE_OT_view(bpy.types.Operator):
    bl_idname='pipe.view'; bl_label='Camera view'
    preset: EnumProperty(items=[('CURRENT','Current',''),('SIDE','Side',''),('OBLIQUE','Oblique',''),('REVERSE','Reverse','')])
    def execute(self,context):
        values={'SIDE':{'camera_yaw':0,'camera_elevation':5},
                'OBLIQUE':{'camera_yaw':22,'camera_elevation':16},
                'REVERSE':{'camera_yaw':158,'camera_elevation':16}}
        if self.preset in values:
            apply_settings(context.scene,values[self.preset])
        for area in context.screen.areas:
            if area.type=='VIEW_3D':
                area.spaces.active.region_3d.view_perspective='CAMERA'
        return {'FINISHED'}


class PIPE_OT_export(bpy.types.Operator):
    bl_idname='pipe.export'; bl_label='Export image + mask'
    randomize: BoolProperty(default=False)
    def execute(self,context):
        try:
            folder=launch_job(context.scene,self.randomize)
            self.report({'INFO'},'Rendering in background: '+str(folder))
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},str(exc)); return {'CANCELLED'}


class PIPE_OT_cancel(bpy.types.Operator):
    bl_idname='pipe.cancel'; bl_label='Stop after current image'
    def execute(self,context):
        if ACTIVE_JOB and ACTIVE_JOB['process'].poll() is None:
            (ACTIVE_JOB['folder']/'cancel.flag').touch()
            self.report({'INFO'},'Will stop after the current image and mask finish.')
        return {'FINISHED'}


class PIPE_OT_test_pipeline(bpy.types.Operator):
    bl_idname='pipe.test_pipeline'; bl_label='Generate lighting test set'
    def execute(self,context):
        global ACTIVE_JOB
        try:
            if ACTIVE_JOB and ACTIVE_JOB['process'].poll() is None:
                raise RuntimeError('An export is already running.')
            from generation_plan import make_plan, write_plan
            p=context.scene.pipe_studio
            environments=('MACHINE','GODSLIGHT') if p.test_environments=='BOTH' else (p.test_environments,)
            plan=make_plan(seed=p.seed,specimens=p.test_specimens,environments=environments,
                           quality=p.test_quality.lower())
            folder=Path(bpy.path.abspath(p.output_dir))/('test_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:5])
            plan_path=write_plan(plan,folder)
            atomic_json(folder/'status.json',{'state':'starting','completed':0,'total':len(plan['samples'])})
            with (folder/'render.log').open('w',encoding='utf-8') as log:
                proc=subprocess.Popen([bpy.app.binary_path,'-b','--factory-startup','--python-exit-code','1',
                    '--python',str(ROOT/'pipeline_runner.py'),'--','--plan',str(plan_path)],stdout=log,
                    stderr=subprocess.STDOUT,cwd=str(ROOT),creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
            ACTIVE_JOB={'process':proc,'folder':folder}; p.last_export=str(folder)
            if not bpy.app.timers.is_registered(poll_job):
                bpy.app.timers.register(poll_job,first_interval=1)
            self.report({'INFO'},f"Generating {len(plan['samples'])} images in background.")
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},str(exc)); return {'CANCELLED'}


class PIPE_OT_report(bpy.types.Operator):
    bl_idname='pipe.report'; bl_label='Open test gallery'
    def execute(self,context):
        folder=Path(context.scene.pipe_studio.last_export)
        path=folder/'report'/'index.html'
        if not path.exists():
            self.report({'INFO'},'The gallery is created when the test set finishes.'); return {'CANCELLED'}
        os.startfile(str(path)); return {'FINISHED'}


class PIPE_OT_open(bpy.types.Operator):
    bl_idname='pipe.open'; bl_label='Open exports'
    image: BoolProperty(default=False)
    def execute(self,context):
        p=context.scene.pipe_studio
        path=Path(p.last_export) if p.last_export else Path(bpy.path.abspath(p.output_dir))
        if self.image:
            latest=read_status(path).get('last_image')
            if not latest:
                self.report({'WARNING'},'No completed image yet.'); return {'CANCELLED'}
            path=Path(latest)
        if not path.exists():
            self.report({'WARNING'},'Export an image first.'); return {'CANCELLED'}
        os.startfile(str(path))
        return {'FINISHED'}


class PIPE_OT_save(bpy.types.Operator):
    bl_idname='pipe.save'; bl_label='Save controls and scene'
    def execute(self,context):
        try:
            refresh(context.scene,geometry=True)
            atomic_json(ROOT/'last_settings.json',settings_dict(context.scene.pipe_studio))
            folder=ROOT/'projects'; folder.mkdir(exist_ok=True)
            path=folder/(context.scene.pipe_studio.product_mode.lower()+'_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid.uuid4().hex[:4]+'.blend')
            save_blend(path)
            self.report({'INFO'},'Saved. The launcher will reuse these controls next time.')
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'},str(exc)); return {'CANCELLED'}


class PIPE_OT_reset(bpy.types.Operator):
    bl_idname='pipe.reset'; bl_label='Reset controls'; bl_options={'REGISTER','UNDO'}
    def execute(self,context):
        p=context.scene.pipe_studio
        apply_settings(context.scene,{key:p.bl_rna.properties[key].default for key in SPEC_KEYS+EXTRA_KEYS})
        p.mask_view=False
        return {'FINISHED'}


class PIPE_PT_main(bpy.types.Panel):
    bl_idname='PIPE_PT_main'; bl_label='Tapered Pipe Studio'
    bl_order=-100
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Pipe Studio'
    def draw(self,context):
        layout=self.layout; p=context.scene.pipe_studio
        if PREFIX+'Pipe' not in bpy.data.objects:
            layout.label(text='Launch with Open Pipe Studio.cmd',icon='INFO'); return
        layout.label(text='Hollow brass pipe • live 3D')
        box=layout.box(); box.label(text='Reference environments',icon='WORLD')
        row=box.row(align=True)
        row.operator('pipe.environment',text='Upright photo').preset='MACHINE'
        row.operator('pipe.environment',text='GodsLight').preset='GODSLIGHT'
        box.operator('pipe.environment',text='Studio').preset='STUDIO'
        box.label(text='Scene: '+p.environment)
        box.prop(p,'lighting_profile',text='Lighting')
        box.operator('pipe.reference',icon='IMAGE_DATA')
        if context.scene.get('pipe_error'):
            box=layout.box(); box.alert=True; box.label(text=context.scene['pipe_error'],icon='ERROR')
        layout.prop(p,'mask_view')
        row=layout.row(align=True)
        row.operator('pipe.view',text='Camera view',icon='VIEW_CAMERA').preset='CURRENT'
        row.operator('render.render',text='Render preview',icon='RENDER_STILL')
        layout.operator('pipe.export',text='Export current image + mask',icon='EXPORT').randomize=False
        if p.last_export:
            status=read_status(p.last_export)
            state=status.get('state','starting')
            box=layout.box()
            box.label(text=f"{state.title()}  {status.get('completed',0)} / {status.get('total','?')}",
                      icon='ERROR' if state=='failed' else 'RENDER_STILL')
            if state in ('starting','rendering'):
                box.operator('pipe.cancel',icon='CANCEL')
            if state=='failed':
                box.label(text='Open exports and inspect render.log.')
            row=box.row(align=True)
            row.operator('pipe.open',text='Folder',icon='FILE_FOLDER')
            row.operator('pipe.open',text='Latest image',icon='IMAGE_DATA').image=True


class PIPE_PT_shape(bpy.types.Panel):
    bl_idname='PIPE_PT_shape'; bl_label='Pipe shape'; bl_parent_id='PIPE_PT_main'
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Pipe Studio'; bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        l=self.layout; p=context.scene.pipe_studio
        l.label(text='Relative scene units; open at both ends.')
        for key in ('length','radius','end_ratio','wall_ratio','body_taper','taper_start','taper_end','shoulder_roundness'):
            l.prop(p,key,slider=True)


class PIPE_PT_defect(bpy.types.Panel):
    bl_idname='PIPE_PT_defect'; bl_label='Surface defect'; bl_parent_id='PIPE_PT_main'
    bl_order=20
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Pipe Studio'
    def draw(self,context):
        l=self.layout; p=context.scene.pipe_studio
        l.prop(p,'defect',expand=True)
        col=l.column(); col.enabled=p.defect!='NONE'
        for key in ('defect_style','defect_rotation','secondary_strength','position','angle','depth','width','arc','irregularity'):
            col.prop(p,key,slider=True)
        col.operator('pipe.front',icon='VIEW_PAN')
        row=l.row(align=True); row.prop(p,'seed'); row.operator('pipe.randomize',text='New defect',icon='FILE_REFRESH')


class PIPE_PT_light(bpy.types.Panel):
    bl_idname='PIPE_PT_light'; bl_label='Brass surface'; bl_parent_id='PIPE_PT_main'
    bl_order=-50
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Pipe Studio'
    def draw(self,context):
        row=self.layout.row(align=True)
        row.operator('pipe.brass_finish',text='Reference').preset='REFERENCE'
        row.operator('pipe.brass_finish',text='Drawn').preset='DRAWN'
        row=self.layout.row(align=True)
        row.operator('pipe.brass_finish',text='Mottled').preset='MOTTLED'
        row.operator('pipe.brass_finish',text='Satin').preset='SATIN'
        for key in ('roughness','texture_strength','wear','oxide_amount','polish_amount','finish_marks','brass_green'):
            self.layout.prop(context.scene.pipe_studio,key,slider=True)


class PIPE_PT_illumination(bpy.types.Panel):
    bl_idname='PIPE_PT_illumination'; bl_label='Lighting controls'; bl_parent_id='PIPE_PT_main'
    bl_order=30
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Pipe Studio'; bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        for key in ('key_power','key_angle','light_azimuth','key_span','light_softness','fill_power',
                    'rim_power','ambient_strength','exposure','tone_mapping','background','color_cast','sensor_noise'):
            self.layout.prop(context.scene.pipe_studio,key,slider=True)


class PIPE_PT_camera(bpy.types.Panel):
    bl_idname='PIPE_PT_camera'; bl_label='Camera'; bl_parent_id='PIPE_PT_main'
    bl_order=40
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Pipe Studio'; bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        l=self.layout; row=l.row(align=True)
        for name,label in [('SIDE','Side'),('OBLIQUE','Oblique'),('REVERSE','Reverse')]:
            row.operator('pipe.view',text=label).preset=name
        for key in ('camera_yaw','camera_elevation','camera_zoom','camera_shift_x','camera_shift_y','frame_aspect','focus_blur'):
            l.prop(context.scene.pipe_studio,key,slider=True)
        l.label(text='Views are adjustable, not calibrated.')


class PIPE_PT_batch(bpy.types.Panel):
    bl_idname='PIPE_PT_batch'; bl_label='Export and batch'; bl_parent_id='PIPE_PT_main'
    bl_order=50
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Pipe Studio'; bl_options={'DEFAULT_CLOSED'}
    def draw(self,context):
        l=self.layout; p=context.scene.pipe_studio
        for key in ('resolution','samples','output_dir','batch_count','clean_fraction','front_only'):
            l.prop(p,key)
        l.operator('pipe.export',text='Generate randomized batch',icon='RENDER_ANIMATION').randomize=True
        l.label(text='PNG + mask + YOLO box + parameters')
        l.separator()
        l.operator('pipe.save',icon='FILE_TICK')
        l.operator('pipe.reset',icon='LOOP_BACK')


class PIPE_PT_test(bpy.types.Panel):
    bl_idname='PIPE_PT_test'; bl_label='Lighting test pipeline'; bl_parent_id='PIPE_PT_main'
    bl_order=60
    bl_space_type='VIEW_3D'; bl_region_type='UI'; bl_category='Pipe Studio'
    def draw(self,context):
        l=self.layout; p=context.scene.pipe_studio
        for key in ('test_environments','test_specimens','test_quality'):
            l.prop(p,key)
        count=p.test_specimens*6*(2 if p.test_environments=='BOTH' else 1)
        l.label(text=f'{count} images / 6 lights per specimen')
        l.label(text='Includes clean and marked clean pipes.')
        l.label(text='Uses reference rigs; seed controls variation.')
        l.operator('pipe.test_pipeline',icon='RENDER_ANIMATION')
        l.operator('pipe.report',icon='IMAGE_DATA')


CLASSES=(PIPE_Settings,PIPE_OT_condition,PIPE_OT_environment,PIPE_OT_reference,PIPE_OT_randomize,PIPE_OT_front,PIPE_OT_view,PIPE_OT_export,PIPE_OT_cancel,PIPE_OT_open,
         PIPE_OT_save,PIPE_OT_reset,PIPE_OT_brass_finish,PIPE_OT_shell_appearance,PIPE_OT_shell_lighting,PIPE_OT_test_pipeline,PIPE_OT_report,PIPE_PT_main,PIPE_PT_shape,PIPE_PT_defect,PIPE_PT_light,PIPE_PT_illumination,PIPE_PT_camera,PIPE_PT_batch,PIPE_PT_test)


def register():
    from workspace_ui import install
    if not getattr(register,'ui_installed',False):
        install(sys.modules[__name__])
        register.ui_installed=True
    for cls in CLASSES:
        bpy.utils.register_class(cls)
    bpy.types.Scene.pipe_studio=PointerProperty(type=PIPE_Settings)
    import rolling_capture
    rolling_capture.register()


def unregister():
    import rolling_capture
    rolling_capture.unregister()
    for timer in (delayed_refresh,poll_job):
        if bpy.app.timers.is_registered(timer):
            bpy.app.timers.unregister(timer)
    del bpy.types.Scene.pipe_studio
    for cls in reversed(CLASSES):
        bpy.utils.unregister_class(cls)


def fresh_scene():
    scene=bpy.data.scenes.new('Pipe Studio')
    bpy.context.window.scene=scene
    return scene


def arrange_view():
    for window in bpy.context.window_manager.windows:
        for area in window.screen.areas:
            if area.type=='VIEW_3D':
                space=area.spaces.active
                space.show_region_ui=True; space.show_region_toolbar=False
                space.overlay.show_overlays=False
                space.shading.type='RENDERED'
                space.shading.use_compositor='CAMERA'
                space.region_3d.view_perspective='CAMERA'
                space.region_3d.view_camera_zoom=8
    return None


def demo(scene,smoke=False):
    from dataclasses import replace
    folder=ROOT/('verification' if smoke else 'examples')
    folder.mkdir(exist_ok=True)
    p=scene.pipe_studio
    base=settings_dict(p)
    if smoke:
        base.update(resolution=320,samples=8,texture_strength=0)
    reports=[]
    variants=[('clean','NONE',155),('dent','DENT',155),('fold','FOLD',155)]
    if smoke:
        variants.append(('hidden','DENT',335))
    for name,kind,angle in variants:
        apply_settings(scene,{**base,'defect':kind,'angle':angle})
        info=export_frame(scene,folder,name)
        reports.append(info)
        if name in ('clean','hidden'):
            assert info['bbox_xywh'] is None, (name,info['bbox_xywh'])
        else:
            assert info['visible_mask_pixels']>10,(name,info['visible_mask_pixels'])
            x,y,w,h=info['bbox_xywh']
            assert x>=0 and y>=0 and x+w<=info['width'] and y+h<=info['height']
            label=(folder/'labels'/(name+'.txt')).read_text()
            assert label.startswith('0 ' if kind=='FOLD' else '1 ')
        assert scene.cycles.samples==base['samples']
        assert scene.view_settings.view_transform=='AgX'
    # Exercise property/operator paths used by the interactive panel.
    apply_settings(scene,base)
    seed=p.seed
    assert bpy.ops.pipe.randomize()=={'FINISHED'}
    assert p.seed==seed+1
    apply_settings(scene,base)
    p.mask_view=True; delayed_refresh()
    assert bpy.data.objects[PREFIX+'Pipe'].data.materials[0].name==PREFIX+'Mask'
    p.mask_view=False; delayed_refresh()
    atomic_json(folder/'verification.json',{'passed':True,'samples':reports})
    save_blend(folder/'Tapered Pipe.blend')
    print('PIPE_STUDIO_VERIFIED',str(folder),flush=True)


def main():
    args=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    parser=argparse.ArgumentParser()
    parser.add_argument('--job'); parser.add_argument('--demo',action='store_true'); parser.add_argument('--smoke',action='store_true')
    parser.add_argument('--preset',choices=list(SCENE_PRESETS))
    parser.add_argument('--reference-demo',action='store_true')
    options=parser.parse_args(args)
    register()
    scene=fresh_scene()
    if options.job:
        run_job(options.job)
        return
    setup_scene(scene)
    if options.reference_demo:
        folder=ROOT/'examples'/'reference-match'; folder.mkdir(parents=True,exist_ok=True)
        reports=[]
        for name in ('MACHINE','GODSLIGHT'):
            apply_settings(scene,{**SCENE_PRESETS[name],'resolution':960,'samples':48})
            reports.append(export_frame(scene,folder,name.lower()))
        atomic_json(folder/'comparison.json',{'samples':reports,'calibrated':False})
        apply_settings(scene,SCENE_PRESETS['MACHINE']); arrange_view()
        save_blend(folder/'Inspection Environments.blend')
        print('REFERENCE_SCENES_READY',str(folder),flush=True)
        return
    if options.demo or options.smoke:
        demo(scene,smoke=options.smoke)
        return
    saved=ROOT/'last_settings.json'
    if options.preset:
        apply_settings(scene,SCENE_PRESETS[options.preset])
    elif saved.exists():
        try:
            apply_settings(scene,json.loads(saved.read_text(encoding='utf-8')))
        except Exception as exc:
            scene['pipe_error']='Saved controls could not load: '+str(exc)
    bpy.app.timers.register(arrange_view,first_interval=.3)
    print('PIPE_STUDIO_READY',scene.get('pipe_device'),flush=True)


if __name__=='__main__':
    main()
